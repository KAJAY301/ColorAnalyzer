use numpy::PyUntypedArrayMethods;
use numpy::ndarray::Array2;
use numpy::{IntoPyArray, PyArray1, PyArray2, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::f64::consts::PI;

use rayon::prelude::*;

/// Converts HSV values in OpenCV's range to cone coordinates, matching Python's hsv_distance.
fn feature(c: [u8; 3]) -> [f64; 3] {
    let (h, s, v) = (c[0] as f64, c[1] as f64, c[2] as f64);
    let a = 2.0 * PI * h / 180.0;
    [
        a.cos() * s / 255.0 * v / 255.0,
        a.sin() * s / 255.0 * v / 255.0,
        v / 255.0 * 2.0,
    ]
}

/// Matches Python's round(distance / sqrt(5) * 255), using ties-to-even rounding.
fn distance(a: &[f64; 3], b: &[f64; 3]) -> f64 {
    let dx = a[0] - b[0];
    let dy = a[1] - b[1];
    let dz = a[2] - b[2];
    let d = (dx * dx + dy * dy + dz * dz).sqrt();
    (d / 5f64.sqrt() * 255.0).round_ties_even()
}

fn group_core(cols: &[[u8; 3]], cnts: &[i64], threshold: f64) -> (Vec<u8>, Vec<i64>) {
    let cell_size = (threshold + 0.5) * 5f64.sqrt() / 255.0;

    let mut rep_color: Vec<[u8; 3]> = Vec::new();
    let mut rep_feat: Vec<[f64; 3]> = Vec::new();
    let mut rep_count: Vec<i64> = Vec::new();
    let mut buckets: HashMap<(i32, i32, i32), Vec<u32>> = HashMap::new();

    for (i, &c) in cols.iter().enumerate() {
        let f = feature(c);
        let cell = (
            (f[0] / cell_size).floor() as i32,
            (f[1] / cell_size).floor() as i32,
            (f[2] / cell_size).floor() as i32,
        );

        // Preserve representative-color order and select the first match, as in Python.
        let mut matched: Option<usize> = None;
        if let Some(list) = buckets.get(&cell) {
            for &ri in list {
                if distance(&f, &rep_feat[ri as usize]) < threshold {
                    matched = Some(ri as usize);
                    break;
                }
            }
        }

        match matched {
            Some(ri) => rep_count[ri] += cnts[i],
            None => {
                let ri = rep_feat.len() as u32;
                rep_color.push(c);
                rep_feat.push(f);
                rep_count.push(cnts[i]);
                for dx in -1..=1 {
                    for dy in -1..=1 {
                        for dz in -1..=1 {
                            buckets
                                .entry((cell.0 + dx, cell.1 + dy, cell.2 + dz))
                                .or_default()
                                .push(ri);
                        }
                    }
                }
            }
        }
    }

    let flat: Vec<u8> = rep_color.iter().flat_map(|c| c.iter().copied()).collect();
    (flat, rep_count)
}

#[pyfunction]
fn count_color<'py>(
    py: Python<'py>,
    pixels: PyReadonlyArray2<'py, u8>,
    colors: PyReadonlyArray2<'py, u8>,
) -> PyResult<(Bound<'py, PyArray2<u8>>, Bound<'py, PyArray1<i64>>)> {
    if pixels.shape()[1] != 3 || colors.shape()[1] != 3 {
        return Err(PyValueError::new_err(
            "pixels and colors must both have shape (N, 3)",
        ));
    }
    let k = colors.shape()[0];
    if k == 0 {
        return Err(PyValueError::new_err("colors must not be empty"));
    }
    let px = pixels
        .as_slice()
        .map_err(|_| PyValueError::new_err("pixels must be a contiguous array (C-contiguous)"))?;
    let n = px.len() / 3;

    // Precompute cosine and sine for hue values 0..255, matching NumPy float32 operation order.
    let mut cos_tab = [0f32; 256];
    let mut sin_tab = [0f32; 256];
    for h in 0..256usize {
        let a = 2.0f32 * std::f32::consts::PI * (h as f32) / 180.0;
        cos_tab[h] = a.cos();
        sin_tab[h] = a.sin();
    }

    let feat = |h: u8, s: u8, v: u8| -> [f32; 3] {
        let sf = s as f32 / 255.0;
        let vf = v as f32 / 255.0;
        [
            cos_tab[h as usize] * sf * vf,
            sin_tab[h as usize] * sf * vf,
            vf * 2.0,
        ]
    };

    // Store the feature vectors and original HSV values for the representative colors.
    let cview = colors.as_array();
    let mut rep_feat: Vec<[f32; 3]> = Vec::with_capacity(k);
    let mut rep_hsv: Vec<[u8; 3]> = Vec::with_capacity(k);
    for i in 0..k {
        let (h, s, v) = (cview[[i, 0]], cview[[i, 1]], cview[[i, 2]]);
        rep_feat.push(feat(h, s, v));
        rep_hsv.push([h, s, v]);
    }

    let mut out = vec![0u8; n * 3];
    const CHUNK: usize = 16_384; // Number of pixels per work unit.

    let counts: Vec<i64> = py.allow_threads(|| {
        px.par_chunks(CHUNK * 3)
            .zip(out.par_chunks_mut(CHUNK * 3))
            .fold(
                || vec![0i64; k],
                |mut acc, (src, dst)| {
                    for (p, o) in src.chunks_exact(3).zip(dst.chunks_exact_mut(3)) {
                        let f = feat(p[0], p[1], p[2]);
                        let mut best = 0usize;
                        let mut best_d = f32::INFINITY;
                        for (j, r) in rep_feat.iter().enumerate() {
                            let dx = f[0] - r[0];
                            let dy = f[1] - r[1];
                            let dz = f[2] - r[2];
                            let d = dx * dx + dy * dy + dz * dz; // Comparing squared distances avoids sqrt.
                            if d < best_d {
                                best_d = d;
                                best = j;
                            }
                        }
                        acc[best] += 1;
                        o.copy_from_slice(&rep_hsv[best]);
                    }
                    acc
                },
            )
            .reduce(
                || vec![0i64; k],
                |mut a, b| {
                    for i in 0..k {
                        a[i] += b[i];
                    }
                    a
                },
            )
    });

    let result =
        Array2::from_shape_vec((n, 3), out).map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((result.into_pyarray(py), PyArray1::from_vec(py, counts)))
}

#[pyfunction]
#[pyo3(signature = (colors, counts, distance_threshold=20))]
fn group_similar_colors<'py>(
    py: Python<'py>,
    colors: PyReadonlyArray2<'py, u8>,
    counts: PyReadonlyArray1<'py, i64>,
    distance_threshold: i64,
) -> PyResult<(Bound<'py, PyArray2<u8>>, Bound<'py, PyArray1<i64>>)> {
    let colors = colors.as_array();
    let counts = counts.as_array();
    let n = colors.nrows();
    if colors.ncols() != 3 || counts.len() != n {
        return Err(PyValueError::new_err(
            "colors must have shape (N, 3), and counts must have shape (N,)",
        ));
    }

    let cols: Vec<[u8; 3]> = (0..n)
        .map(|i| [colors[[i, 0]], colors[[i, 1]], colors[[i, 2]]])
        .collect();
    let cnts: Vec<i64> = counts.to_vec();

    // Release the GIL during computation.
    let (flat, rep_count) =
        py.allow_threads(|| group_core(&cols, &cnts, distance_threshold as f64));

    let m = rep_count.len();
    let reps =
        Array2::from_shape_vec((m, 3), flat).map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((reps.into_pyarray(py), PyArray1::from_vec(py, rep_count)))
}

#[pymodule]
fn color_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(group_similar_colors, m)?)?;
    m.add_function(wrap_pyfunction!(count_color, m)?)?;
    Ok(())
}
