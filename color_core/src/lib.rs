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
fn find_background_color<'py>(
    pixels: PyReadonlyArray2<'py, u8>,
    colors: PyReadonlyArray2<'py, u8>,
    width: usize,
) -> PyResult<(u8, u8, u8)> {
    if pixels.shape()[1] != 3 || colors.shape()[1] != 3 {
        return Err(PyValueError::new_err(
            "pixels and colors must both have shape (N, 3)",
        ));
    }

    let px = pixels
        .as_slice()
        .map_err(|_| PyValueError::new_err("pixels must be contiguous"))?;

    let color_view = colors.as_array();

    let n = px.len() / 3;
    let k = colors.shape()[0];

    if n == 0 || width == 0 || n % width != 0 {
        return Err(PyValueError::new_err("Invalid image dimensions"));
    }

    if k == 0 {
        return Err(PyValueError::new_err("colors must not be empty"));
    }

    let height = n / width;

    // Pack HSV into a single u32 for fast comparison.
    let pack = |h: u8, s: u8, v: u8| -> u32 {
        ((h as u32) << 16) | ((s as u32) << 8) | (v as u32)
    };

    // Build sorted color lookup table.
    let mut lookup: Vec<(u32, usize)> = (0..k)
        .map(|i| {
            (
                pack(
                    color_view[[i, 0]],
                    color_view[[i, 1]],
                    color_view[[i, 2]],
                ),
                i,
            )
        })
        .collect();

    lookup.sort_unstable_by_key(|entry| entry.0);

    // Bounding box storage.
    let mut min_x = vec![width; k];
    let mut min_y = vec![height; k];
    let mut max_x = vec![0usize; k];
    let mut max_y = vec![0usize; k];

    // Scan every pixel exactly once.
    for (i, p) in px.chunks_exact(3).enumerate() {
        let key = pack(p[0], p[1], p[2]);

        let pos = lookup
            .binary_search_by_key(&key, |entry| entry.0)
            .map_err(|_| PyValueError::new_err(
                "Pixel color not found in candidates"
            ))?;

        let color_idx = lookup[pos].1;

        let x = i % width;
        let y = i / width;

        min_x[color_idx] = min_x[color_idx].min(x);
        min_y[color_idx] = min_y[color_idx].min(y);

        max_x[color_idx] = max_x[color_idx].max(x);
        max_y[color_idx] = max_y[color_idx].max(y);
    }

    // Find the largest bounding box.
    let mut best_idx = 0;
    let mut best_area = 0usize;

    for i in 0..k {
        let bbox_area =
            (max_x[i] - min_x[i] + 1) *
            (max_y[i] - min_y[i] + 1);

        if bbox_area > best_area {
            best_area = bbox_area;
            best_idx = i;
        }
    }

    Ok((
        color_view[[best_idx, 0]],
        color_view[[best_idx, 1]],
        color_view[[best_idx, 2]],
    ))
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
    m.add_function(wrap_pyfunction!(find_background_color, m)?)?;
    m.add_function(wrap_pyfunction!(count_color, m)?)?;
    Ok(())
}
