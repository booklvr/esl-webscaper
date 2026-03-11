# extract-textbook-content

TSherpa teacher textbook extractor that:

1. reads the archive page,
2. finds chapter PDFs in the `지도서 PDF` row,
3. downloads each PDF,
4. sends each PDF to OpenAI,
5. extracts target language (`vocab`, `expressions`, `questions`) per chapter,
6. writes JSON + CSV outputs.

## Usage

```bash
export OPENAI_API_KEY="..."
python extract-textbook-content/tsherpa_teacher_pdf.py \
  --archive-url "https://cdata2.tsherpa.co.kr/ebook/tsherpa/22/22ebook_E/TB2022TC1EE_30K/resource/include/archive/index.html" \
  --out-dir data/tsherpa
```

Outputs:

- `data/tsherpa/teacher_pdf_extraction.json`
- `data/tsherpa/teacher_pdf_extraction.csv`
- `data/tsherpa/pdfs/*.pdf`
