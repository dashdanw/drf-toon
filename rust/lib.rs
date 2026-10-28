//! Experimental native TOON codec for drf-toon, backed by the `toon-format` Rust crate.

use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde_json::Value;

create_exception!(_native, ToonDecodeError, PyException);

fn to_py(py: Python<'_>, value: Value) -> PyResult<Bound<'_, PyAny>> {
    Ok(match value {
        Value::Null => py.None().into_bound(py),
        Value::Bool(b) => b.into_pyobject(py)?.to_owned().into_any(),
        Value::Number(n) => {
            // `arbitrary_precision` keeps the literal, so big integers survive as Python ints.
            let literal = n.to_string();
            if literal.bytes().all(|b| b.is_ascii_digit() || b == b'-') {
                py.get_type::<pyo3::types::PyInt>().call1((literal,))?
            } else {
                n.as_f64().unwrap_or(f64::NAN).into_pyobject(py)?.into_any()
            }
        }
        Value::String(s) => s.into_pyobject(py)?.into_any(),
        Value::Array(items) => {
            let list = PyList::empty(py);
            for item in items {
                list.append(to_py(py, item)?)?;
            }
            list.into_any()
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, to_py(py, v)?)?;
            }
            dict.into_any()
        }
    })
}

/// True when `value` holds an integer outside the i64/u64 range, which `toon-format` 0.7 can
/// only represent by rounding through f64.
fn has_oversized_int(value: &Value) -> bool {
    match value {
        Value::Number(n) => {
            n.as_i64().is_none()
                && n.as_u64().is_none()
                && n.to_string().bytes().all(|b| b.is_ascii_digit() || b == b'-')
        }
        Value::Array(items) => items.iter().any(has_oversized_int),
        Value::Object(map) => map.values().any(has_oversized_int),
        _ => false,
    }
}

/// JSON document (bytes) -> TOON text. Lets the renderer skip a `json.loads` round trip.
///
/// Returns `None` when the document can't be encoded losslessly (integers beyond 64 bits);
/// callers should fall back to another codec.
#[pyfunction]
fn encode_json(py: Python<'_>, json: &[u8]) -> PyResult<Option<String>> {
    let value: Value = serde_json::from_slice(json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    if has_oversized_int(&value) {
        return Ok(None);
    }
    py.detach(|| toon_format::encode_default(&value))
        .map(Some)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

/// TOON text -> Python objects (dict/list/str/int/float/bool/None), strict mode.
#[pyfunction]
fn decode<'py>(py: Python<'py>, text: &str) -> PyResult<Bound<'py, PyAny>> {
    let value: Value = py
        .detach(|| toon_format::decode_strict(text))
        .map_err(|e| ToonDecodeError::new_err(e.to_string()))?;
    to_py(py, value)
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_json, m)?)?;
    m.add_function(wrap_pyfunction!(decode, m)?)?;
    m.add("ToonDecodeError", m.py().get_type::<ToonDecodeError>())?;
    Ok(())
}
