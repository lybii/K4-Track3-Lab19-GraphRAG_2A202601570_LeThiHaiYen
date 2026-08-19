# Phân tích ca lỗi — Flat RAG và GraphRAG

**Học viên:** Lê Thị Hải Yến  
**MSV:** 2A202601570  
**Phạm vi:** 765 chunks, 42 graph nodes, 24 graph edges, 5 Golden queries.

## Ca lỗi 1 — Multi-hop retrieval thất bại

**Câu hỏi:** G02 và G04.  
**Expected path:** `Tower Arch Capital -INVESTED_IN-> Intelligent Technical Solutions -ACQUIRED-> Granite Computer Solutions/BrightWire Networks`.

### Triệu chứng

Cả Flat RAG và GraphRAG đều trả lời không đủ evidence. Judge chấm 1/5 cho comprehensiveness, faithfulness và multi-hop reasoning.

### Root cause

- Flat RAG: cosine retrieval không mô hình hóa path constraint, nên top-k không giữ đủ hai facts theo đúng vai trò.
- GraphRAG: path có trong Neo4j nhưng seed extraction/type matching không resolve được `Tower Arch Capital`; BFS vì thế không thu thập cạnh.
- Hybrid fallback không cứu được câu hỏi vì vector context cũng thiếu path.

### Khắc phục

Thêm deterministic n-gram/entity dictionary trước LLM seed extraction; log `matched_seeds`; exact match không phụ thuộc type do LLM đoán; fallback fuzzy có threshold; và unit test path recall cho từng Golden query.

## Ca lỗi 2 — Graph context/generator phủ nhận fact có thật

**Câu hỏi:** G01 về Samsung Electronics và relation `DEVELOPED`.  
**Reference:** `analog semiconductor technology`.

### Triệu chứng

Graph chứa cạnh đúng nhưng GraphRAG trả lời không tìm thấy relation. Flat RAG tìm thấy nội dung nhưng mở rộng thêm “logic”, khiến answer lệch reference hẹp.

### Root cause

- Seed/type mismatch hoặc serialization làm cạnh không xuất hiện trong context cuối.
- Generator không có assertion buộc kiểm tra trực tiếp các edge đã linearize.
- Golden answer hẹp hơn nội dung chunk nên Judge trừ điểm câu trả lời có thêm fact dù fact có evidence.

### Khắc phục

Ghi diagnostics cho seed, edges, context chars; validate rằng expected edge xuất hiện trước generation; dùng structured graph facts thay vì chỉ chuỗi tự do; và thiết kế reference/scoring notes cho phép additional supported facts.

## Ca lỗi 3 — Extraction noise

Chunk `46de4639bae27ff41d8a::c0000` tạo `Charlie -WORKED_AT-> ISG` từ câu giới thiệu người điều phối. Đây là false positive do quan hệ bị suy diễn quá mức.

Khắc phục bằng evidence entailment pass, relation-specific verb allowlist, confidence calibration và human review cho cạnh tác động cao.

## Kết luận

Failure modes xuất hiện ở cả extraction, entity/seed resolution, retrieval và evaluation contract. Cần metrics tách tầng: extraction precision, seed recall, edge/path recall, context sufficiency và answer faithfulness; chỉ dùng điểm câu trả lời cuối sẽ không chỉ ra đúng nguyên nhân.
