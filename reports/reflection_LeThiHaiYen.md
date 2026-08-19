# Reflection và Action Plan — Lê Thị Hải Yến

**MSV:** 2A202601570

## Mapping bài giảng vào code

| Khái niệm | Hàm/khối code | Quan sát |
|---|---|---|
| Conservative coreference | `resolve_coref_batch()`, `run_coref()` | Checkpoint cần thiết vì API chậm/rate-limit |
| Schema allowlist | `ALLOWED_NODE_TYPES`, `ALLOWED_RELATIONS` | Loại output ngoài schema trước ingestion |
| Bulk ingestion | `bulk_insert_nodes()`, `bulk_insert_edges()` | `UNWIND` giảm round trips; cần reconnect Aura |
| Entity resolution | `build_resolution_map()`, `merge_guard()`, `UF` | ANN candidate không được thay thế lexical/type guard |
| Flat RAG | `build_flat_index()`, `retrieve_flat_context()` | 765 vectors với `IndexFlatIP` |
| Graph traversal | `retrieve_graph_context()` | Seed recall quyết định path recall |
| Super-node mitigation | cap 50/250/14.000 | Subset nhỏ chưa có node degree >100 |
| LLM Judge | `judge_answer()`, `run_evaluation()` | Cần checkpoint và scoring notes rõ |

## Lỗi khó nhất và bài học

Pipeline gặp một chuỗi lỗi độc lập: dataset gated, model Groq cũ trả 404, model khác hết quota, NumPy/Protobuf không tương thích TensorFlow, JSON model trả sai kiểu, và Neo4j connection stale. Tôi giải quyết bằng kiểm tra dịch vụ độc lập, pin dependency, type guard, retry/reconnect và checkpoint sau từng stage.

Bài học lớn nhất là hệ thống RAG production phải resumable, observable và fail-fast. Không nên nuốt lỗi batch rồi để module sau báo DataFrame rỗng; mỗi stage phải xuất count, error sample và invariant.

## Action Plan đồ án

**Đề xuất:** Trợ lý phân tích tin tức công nghệ và quan hệ doanh nghiệp.

GraphRAG chỉ được route cho câu hỏi multi-hop, temporal hoặc cross-document. Factoid đơn giản dùng Flat RAG để giảm latency.

- Nodes: `Company`, `Person`, `Technology`, `Product`, `Event`.
- Relations: `ACQUIRED`, `INVESTED_IN`, `FOUNDED`, `WORKED_AT`, `DEVELOPED`, `USES`, `PARTNERED_WITH`, `LEADS`.
- Entity resolution: alias map, type blocking, ANN, lexical guard và review vùng không chắc chắn.
- Super-node: temporal intent, relation quotas, community partition và global cap.
- Evaluation: extraction precision, seed recall, path recall, faithfulness, latency và cost.

Mục tiêu triển khai là hybrid router: câu hỏi đơn giản đi vector path; câu hỏi có path constraint đi graph path; nếu graph context không đủ thì self-correction mở rộng hop rồi vector fallback.
