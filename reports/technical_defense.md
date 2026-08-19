# Thuyết minh kỹ thuật — Lab 19 GraphRAG vs Flat RAG

**Học viên:** Lê Thị Hải Yến  
**MSV:** 2A202601570  
**Ngày thực hiện:** 19/08/2026

## 1. Vì sao dùng conservative coreference?

False coreference tạo false edge có sức lan truyền lớn hơn một mention bị bỏ sót. Pipeline chỉ thay đại từ khi antecedent xuất hiện rõ trong cùng chunk; trường hợp mơ hồ được giữ nguyên và ghi `unresolved_mentions`. Ví dụ chunk `46de4639bae27ff41d8a::c0000` tạo `Charlie -WORKED_AT-> ISG` dù evidence chỉ nói Charlie điều phối cuộc gọi. Production cần thêm relation-specific evidence guard để loại cạnh này.

## 2. Threshold Entity Resolution được chọn thế nào?

Ngưỡng vector merge là `0.90`, sau đó lexical guard yêu cầu SequenceMatcher tối thiểu `0.72`. Ngưỡng cao ưu tiên precision vì false merge làm hợp nhất toàn bộ cạnh của hai entity. ANN chỉ sinh candidate; quyết định cuối vẫn cần cùng type và lexical guard.

## 3. Ví dụ Lexical Guard từ chối merge

Subset không có cặp khác nhau đạt cosine trên `0.85`; tôi không tạo số liệu giả. Cặp gần nhất là `logic semiconductor technology` và `advanced semiconductor technology`, cosine `0.703044`, quyết định `REJECT_GUARD`. Hai tên cùng miền nhưng chỉ một tên nói logic, tên kia nói phạm vi advanced rộng hơn.

## 4. Provenance được bảo đảm ra sao?

Mọi edge có `source_chunk_id`, `published_date`, `evidence`, `confidence`. Sanity query sau ingestion trả `invalid_provenance_edges = 0`. Graph cuối có 42 nodes và 24 edges. Ingestion dùng `UNWIND` theo batch, không round-trip từng row.

## 5. Chính sách Super-node

Nếu degree lớn hơn 100, traversal chỉ lấy tối đa 50 cạnh mới nhất. Toàn request có `GLOBAL_EDGE_CAP=250` và `MAX_GRAPH_CONTEXT_CHARS=14000`. Subset hiện tại chưa có super-node thật; ba node cao nhất đều degree 3. Notebook bổ sung unit test mô phỏng degree 101 và 10.000: edge budget bằng 50, global cap bằng 250 và context cap bằng 14.000 ký tự.

## 6. Vì sao ưu tiên cạnh mới nhất có rủi ro?

Nó phù hợp truy vấn tin tức hiện hành và kiểm soát token, nhưng có thể cắt mất sự kiện lịch sử. Cải tiến là nhận diện temporal intent, lọc theo khoảng ngày của câu hỏi và cấp quota riêng cho từng relation type.

## 7. Flat RAG thất bại ở đâu?

G02/G04 yêu cầu đường đi `Tower Arch Capital -INVESTED_IN-> Intelligent Technical Solutions -ACQUIRED-> Granite Computer Solutions/BrightWire Networks`. Vector top-k không bảo đảm nối đúng hai vai trò quan hệ, nên Flat RAG trả lời thiếu thông tin.

## 8. GraphRAG thất bại ở đâu?

Graph có đúng đường đi G02/G04 nhưng seed extraction/matching không đưa node vào BFS context. Ở G01 graph cũng có cạnh Samsung `DEVELOPED` analog semiconductor technology, nhưng generator phủ nhận cạnh. Điều này chứng minh chất lượng graph không đồng nghĩa chất lượng retrieval và generation.

## 9. Trade-off thực nghiệm

| Metric trung bình | Flat RAG | GraphRAG |
|---|---:|---:|
| Comprehensiveness | 1.80 | 1.00 |
| Faithfulness | 1.80 | 1.00 |
| Multi-hop reasoning | 1.80 | 1.00 |
| Latency (s) | 8.57 | 22.00 |
| Tokens | 1,101.6 | 739.4 |

GraphRAG dùng ít token hơn nhưng chậm và kém chính xác trong sample. Token thấp không phải lợi ích nếu context thiếu evidence.

## 10. Scale lên 350 MB

Bottleneck đầu tiên là LLM extraction/rate limit, tiếp theo là entity resolution và graph writes. Thiết kế cần stream ingestion, near-dedup, durable queue, idempotent checkpoint theo shard, dead-letter queue, ANN blocking theo type, `UNWIND` batch, telemetry chi phí và incremental indexing. Tôi từ chối chạy extraction toàn corpus khi model/quota/checkpoint chưa được xác nhận.

## Bonus đã kiểm chứng

NetworkX đã phân cụm 42 nodes thành 18 communities, nạp `community_id` vào Neo4j và sinh `outputs/community_reports.csv`. Global context ưu tiên đúng community Tower Arch Capital/Intelligent Technical Solutions cho câu hỏi quan hệ doanh nghiệp. Self-Correction trên G02 đã thử hop 2, hop 3 rồi chuyển sang `hop3+vector`; checkpoint ghi context 2.299 ký tự.
