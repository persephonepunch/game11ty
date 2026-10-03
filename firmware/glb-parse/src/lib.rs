//! Parse the JSON chunk of a GLB file from untrusted bytes, with no OS and no heap.
#![cfg_attr(not(test), no_std)]

#[derive(Debug, PartialEq)]
pub enum GlbError { NotGlb, Truncated, LengthLie }

fn u32_at(data: &[u8], at: usize) -> Result<u32, GlbError> {
    // .get() returns None instead of reading past the end: no buffer overflow possible.
    let b = data.get(at..at.checked_add(4).ok_or(GlbError::Truncated)?).ok_or(GlbError::Truncated)?;
    Ok(u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
}

/// Returns the JSON chunk as a borrowed slice of the input: no copy, no allocation,
/// and the borrow checker guarantees the result can't outlive the buffer it points into.
pub fn glb_json(data: &[u8]) -> Result<&[u8], GlbError> {
    if data.get(0..4) != Some(b"glTF") { return Err(GlbError::NotGlb); }
    if u32_at(data, 8)? as usize != data.len() { return Err(GlbError::LengthLie); }
    let len = u32_at(data, 12)? as usize;
    if data.get(16..20) != Some(b"JSON") { return Err(GlbError::NotGlb); }
    // checked_add: on a 32-bit microcontroller, 20 + 0xFFFF_FFFF would wrap around in C.
    let end = 20usize.checked_add(len).ok_or(GlbError::LengthLie)?;
    data.get(20..end).ok_or(GlbError::LengthLie)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn glb(json: &[u8], declared_chunk: u32, declared_total: Option<u32>) -> Vec<u8> {
        let total = (20 + json.len()) as u32;
        let mut v = b"glTF".to_vec();
        v.extend(2u32.to_le_bytes()); v.extend(declared_total.unwrap_or(total).to_le_bytes());
        v.extend(declared_chunk.to_le_bytes()); v.extend(b"JSON"); v.extend(json); v
    }
    #[test] fn allow_valid() { let j = br#"{"asset":{}}"#; assert_eq!(glb_json(&glb(j, j.len() as u32, None)), Ok(&j[..])); }
    #[test] fn block_not_glb() { assert_eq!(glb_json(b"MZ\x90\x00 not a model........"), Err(GlbError::NotGlb)); }
    #[test] fn fail_closed_empty() { assert_eq!(glb_json(b""), Err(GlbError::NotGlb)); }
    #[test] fn block_truncated_header() { assert_eq!(glb_json(b"glTF\x02\x00"), Err(GlbError::Truncated)); }
    #[test] fn block_total_length_lie() { let j = b"{}"; assert_eq!(glb_json(&glb(j, 2, Some(999))), Err(GlbError::LengthLie)); }
    #[test] fn boundary_chunk_one_byte_past_end() { let j = b"{}  "; assert_eq!(glb_json(&glb(j, 5, None)), Err(GlbError::LengthLie)); }
    #[test] fn block_wrong_first_chunk() {
        let mut v = glb(b"{}", 2, None); v[16..20].copy_from_slice(b"BIN\0");
        assert_eq!(glb_json(&v), Err(GlbError::NotGlb));
    }
    #[test] fn evasion_chunk_length_wraps_u32() { let j = b"{}"; assert_eq!(glb_json(&glb(j, u32::MAX, None)), Err(GlbError::LengthLie)); }
}
