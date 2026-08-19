# Báo Cáo Thực Hành & Thuyết Minh Kỹ Thuật — Lab 19: GraphRAG vs Flat RAG

**Học viên:** Lê Thị Hải Yến  
**Khóa học:** AICB-K34 · Track 3: GraphRAG  
**Ngày thực hiện:** 19/08/2026  

## PHẦN 1 — THUYẾT MINH KỸ THUẬT VÀ PHÂN TÍCH CA LỖI

### 1. Coreference Resolution

Pipeline chạy conservative coreference trên 40 chunks và lưu checkpoint tại `outputs/coref_checkpoint.jsonl`. Một tình huống khó nằm trong chunk `46de4639bae27ff41d8a::c0000`: câu “My name is Charlie and Charlie will be coordinating the call today” dẫn mô hình tới triple `Charlie -WORKED_AT-> ISG`. Văn bản chỉ chứng minh Charlie điều phối cuộc gọi, không chứng minh quan hệ lao động. Đây không chỉ là lỗi coreference mà còn là lỗi diễn giải quan hệ: một mention được phân giải quá tự tin có thể tạo false edge, rồi false edge tiếp tục xuất hiện trong BFS context và câu trả lời cuối.

Biện pháp đã dùng là chỉ thay đại từ khi antecedent xuất hiện rõ trong cùng chunk; nếu mơ hồ thì giữ nguyên và ghi `unresolved_mentions`. Trong production, tôi sẽ thêm rule không cho `WORKED_AT` nếu evidence không có động từ employment rõ ràng, đồng thời đưa các batch thất bại vào hàng đợi review thay vì âm thầm chấp nhận.

### 2. Entity Resolution Threshold và Lexical Guard

Ngưỡng merge vector được giữ ở `0.90`; lexical guard yêu cầu SequenceMatcher sau khi bỏ hậu tố doanh nghiệp đạt ít nhất `0.72`. Entity Resolution dùng FAISS ANN để sinh ứng viên, sau đó mới áp dụng guard và Union-Find. Audit thực tế có 44 ứng viên được ghi log, lớn hơn yêu cầu 10 dòng.

Trong subset này không có cặp khác nhau đạt cosine trên `0.85`; vì vậy tôi không tạo số liệu giả để đáp ứng câu hỏi. Cặp bị từ chối gần nhất là `logic semiconductor technology` và `advanced semiconductor technology`, cosine `0.703044`. Hai cụm cùng miền bán dẫn nhưng không đồng nhất về nghĩa, nên quyết định `REJECT_GUARD` là đúng. Hai cặp tiếp theo là `analog semiconductor technology` với `logic semiconductor technology` (`0.673070`) và với `advanced semiconductor technology` (`0.619584`). Kết quả cũng cho thấy threshold `0.90` khá bảo thủ: giảm threshold chỉ để tăng recall sẽ tạo false merge giữa các công nghệ liên quan nhưng khác nhau.

### 3. Đồ thị và Super-node Mitigation

Đồ thị sau ingestion có **42 nodes, 24 edges và 0 cạnh thiếu provenance**.

| Hạng | Thực thể | Loại | Degree |
|---:|---|---|---:|
| 1 | Intelligent Technical Solutions | Company | 3 |
| 2 | Samsung Electronics Co. Ltd. | Company | 3 |
| 3 | Walt Disney Co. | Company | 3 |

Subset 40 extraction chunks chưa sinh node có degree lớn hơn 100, nên test thực tế chọn node cao nhất và lấy đúng 3/3 cạnh. Chính sách vẫn được cài đặt: `degree > 100` thì lấy tối đa 50 cạnh mới nhất; toàn context tối đa 250 cạnh và 14.000 ký tự.

Ưu điểm của ưu tiên cạnh mới nhất là kiểm soát context explosion và phù hợp câu hỏi tin tức hiện hành. Rủi ro là câu hỏi lịch sử có thể mất cạnh cũ quan trọng. Production nên kết hợp temporal filter theo intent câu hỏi, relation-aware sampling và quota theo loại cạnh thay vì chỉ sort ngày toàn cục.

### 4. Benchmark Flat RAG và GraphRAG

Golden Dataset gồm 5 câu: 1 factoid, 2 multi-hop và 2 cross-doc. Judge dùng `openai/gpt-oss-20b` qua Groq.

| Tiêu chí | Flat RAG | GraphRAG | Δ Graph − Flat | Nhận xét |
|---|---:|---:|---:|---|
| Comprehensiveness | 1.80 | 1.00 | -0.80 | Graph retrieval thường không tìm được seed/cạnh cần thiết |
| Faithfulness | 1.80 | 1.00 | -0.80 | Graph answer thêm hoặc phủ nhận thông tin trái reference |
| Multi-hop reasoning | 1.80 | 1.00 | -0.80 | Chuỗi đúng có trong graph nhưng không được đưa vào context |
| Latency trung bình (s) | 8.57 | 22.00 | +13.43 | GraphRAG chậm hơn do seed extraction, Cypher và hybrid generation |
| Token usage trung bình | 1,101.6 | 739.4 | -362.2 | GraphRAG dùng ít token hơn do graph context nhỏ/rỗng |

#### Ca lỗi Flat RAG

Ở G02/G04, câu hỏi yêu cầu chuỗi `Tower Arch Capital -INVESTED_IN-> Intelligent Technical Solutions -ACQUIRED-> Granite Computer Solutions/BrightWire Networks`. Flat RAG trả lời thiếu bằng chứng vì top-k vector chunks không lấy được chuỗi theo cấu trúc. Đây là failure mode điển hình của retrieval thuần similarity: hai facts có thể nằm trong cùng corpus nhưng query embedding không bảo đảm nối đúng vai trò source/intermediate/target.

#### Ca lỗi GraphRAG

GraphRAG cũng thất bại ở G02/G04 dù Neo4j thực sự chứa chuỗi hai hop. Nguyên nhân gốc là seed extraction/matching không đưa `Tower Arch Capital` tới đúng node, nên BFS context rỗng và hybrid generator chỉ còn vector context. Ở G01, graph có cạnh `Samsung Electronics Co. Ltd. -DEVELOPED-> analog semiconductor technology`, nhưng câu trả lời lại nói không tìm thấy quan hệ. Điều này cho thấy “graph đúng” chưa đủ; seed resolution, direction của edge, context serialization và prompt grounding đều là các điểm có thể làm hỏng hệ thống.

Khắc phục đề xuất: thêm deterministic entity lookup từ n-gram trước LLM seed extraction; log `matched_seeds`; cho phép exact `name_norm` không phụ thuộc type do LLM đoán; khi graph context rỗng thì retry fuzzy threshold có kiểm soát; và thêm retrieval unit test cho từng Golden path.

### 5. Trade-offs, kiểm soát AI Coding Agent và scale 350 MB

Flat RAG có indexing đơn giản và latency thấp hơn, nhưng yếu ở compositional questions. GraphRAG tốn thêm coreference, extraction, entity resolution, Neo4j ingestion và traversal. Trong thử nghiệm này GraphRAG không tăng chất lượng, nhưng giảm token generation khoảng 33%; phần giảm token chủ yếu do context graph nhỏ nên không thể xem là lợi ích nếu câu trả lời sai.

Tôi từ chối hướng tăng extraction lên toàn bộ dataset ngay khi pipeline chưa có checkpoint và quota guard. Lần chạy 400 chunks đã chạm quota model và tạo retry kéo dài; giải pháp đúng là checkpoint theo giai đoạn, xác nhận model availability trước, chạy pilot 40 chunks và chỉ scale khi metrics ổn định. Tôi cũng không dùng pairwise entity comparison O(N²), mà dùng FAISS ANN rồi lexical guard.

Khi scale toàn bộ khoảng 350 MB, bottleneck đầu tiên là LLM extraction và retry/rate limit, sau đó là entity resolution và graph write throughput. Kiến trúc đề xuất gồm stream ingestion, content hash/near-dedup, durable work queue, idempotent batch extraction, checkpoint theo shard, HNSW/FAISS với blocking theo type, Neo4j `UNWIND` batch, dead-letter queue, cost/latency telemetry và incremental re-indexing. Không nên tải toàn bộ corpus vào RAM hoặc gửi toàn bộ qua LLM trong một job.

## PHẦN 2 — REFLECTION VÀ ACTION PLAN

### 1. Mapping bài giảng vào code

| Khái niệm | Module | Hàm/khối code | Quan sát thực tế |
|---|---|---|---|
| Conservative Coreference | M1 | `resolve_coref_batch()`, `run_coref()` | Cần checkpoint và validation quan hệ sau coreference |
| Schema & Allowlist Guard | M2 | `ALLOWED_NODE_TYPES`, `ALLOWED_RELATIONS`, `run_extraction()` | Lọc model output sai schema trước ingestion |
| Bulk Cypher Ingestion | M2 | `bulk_insert_nodes()`, `bulk_insert_edges()` | Dùng `UNWIND`; reconnect khi Aura connection stale |
| Entity Resolution | M3 | `build_resolution_map()`, `merge_guard()`, `UF` | Threshold 0.90 ngăn merge các công nghệ gần nghĩa |
| Flat RAG | M4 | `build_flat_index()`, `retrieve_flat_context()` | Index 765 chunks bằng `IndexFlatIP` |
| Super-node cap | M4 | `retrieve_graph_context()` | Cài cap 50/250/14.000; subset chưa có super-node thật |
| LLM-as-a-Judge | M5 | `judge_answer()`, `run_evaluation()` | Cần checkpoint vì mỗi câu có nhiều API calls |

### 2. Debugging và bài học

Lỗi khó nhất là chuỗi lỗi môi trường và dịch vụ: dataset gated; model Groq cũ trả 404; Qwen chạm giới hạn 200.000 token/ngày do retry; NumPy 2.x không tương thích TensorFlow; model trả `items` sai kiểu; và kết nối Neo4j stale trong lúc ingestion. Tôi xử lý bằng cách xác nhận từng dependency độc lập, chuyển sang model khả dụng `openai/gpt-oss-20b`, pin `numpy<2`, thêm type guard cho JSON, checkpoint coreference/triples/evaluation và retry reconnect Neo4j.

Bài học quan trọng là pipeline production phải observable và resumable. Không được nuốt lỗi batch rồi chỉ phát hiện DataFrame rỗng ở module sau; mỗi stage cần count, error sample, checkpoint và fail-fast invariant.

### 3. Kế hoạch áp dụng vào đồ án thực tế

**Tên đề xuất:** Trợ lý phân tích tin tức công nghệ và quan hệ doanh nghiệp.

GraphRAG phù hợp khi người dùng hỏi chuỗi đầu tư–mua lại–phát triển công nghệ hoặc so sánh sự kiện qua nhiều bài. Với câu factoid đơn giản, Flat/Hybrid RAG rẻ và nhanh hơn; router nên chọn GraphRAG chỉ khi query có dấu hiệu multi-hop, temporal hoặc cross-document.

- Nodes: `Company`, `Person`, `Technology`, có thể mở rộng `Product`, `Event`.
- Relations: `ACQUIRED`, `INVESTED_IN`, `FOUNDED`, `WORKED_AT`, `DEVELOPED`, `USES`, `PARTNERED_WITH`, `LEADS`.
- Entity Resolution: alias dictionary + type blocking + ANN candidates + lexical guard + manual review cho vùng similarity không chắc chắn.
- Super-node: filter theo thời gian/query intent, quota theo relation type, community partition và global edge/context cap.
- Evaluation: Golden paths lấy từ graph đã kiểm chứng, retrieval recall@k cho seed/edge/path, answer faithfulness và latency/cost dashboard.

## TỰ ĐÁNH GIÁ

### Bonus đã thực hiện

- **Global Search via Community Reports:** NetworkX phát hiện 18 communities và gán `community_id` cho đủ 42 nodes. `outputs/community_reports.csv` chứa summary từng cộng đồng; global query đã ưu tiên đúng cluster Tower Arch Capital → Intelligent Technical Solutions → các công ty được mua lại.
- **Self-Correction Graph Retrieval:** demo trên G02 thử hop 2, mở rộng hop 3 rồi dùng vector fallback. Route cuối là `hop3+vector`, context dài 2.299 ký tự; kết quả được lưu tại `outputs/self_correction_demo.json`.

| Tiêu chí | Điểm (1–5) | Ghi chú |
|---|---:|---|
| Hiểu GraphRAG | 4 | Hiểu đầy đủ extraction, resolution, traversal và failure modes |
| Kiểm soát AI Coding Agent | 4 | Không scale mù; kiểm tra quota/model/schema trước |
| Chất lượng Knowledge Graph | 3 | Provenance đầy đủ nhưng subset nhỏ và extraction còn noise |
| Phân tích và debug hệ thống | 5 | Truy vết được lỗi qua dataset, API, parser, dependency và database |
