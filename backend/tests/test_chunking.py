from app.ingest import chunk_text
def test_chunking_has_overlap():
    text=" ".join(f"w{i}" for i in range(100))
    chunks=chunk_text(text,30,5)
    assert len(chunks)>1
    assert chunks[0].split()[-5:]==chunks[1].split()[:5]
