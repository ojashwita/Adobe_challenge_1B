import json
import os
import re
from typing import List, Dict, Tuple, Any
import fitz  # PyMuPDF
from collections import defaultdict, Counter
from datetime import datetime

class PersonaDrivenAnalyzer:
    def __init__(self):
        # Domain-specific keywords for different personas
        self.persona_keywords = {
            'researcher': {
                'methodology', 'approach', 'method', 'algorithm', 'experiment', 'results',
                'analysis', 'evaluation', 'performance', 'dataset', 'benchmark', 'model',
                'framework', 'technique', 'implementation', 'validation', 'comparison'
            },
            'student': {
                'definition', 'concept', 'principle', 'theory', 'example', 'formula',
                'equation', 'problem', 'solution', 'exercise', 'practice', 'review',
                'summary', 'key points', 'important', 'remember', 'note'
            },
            'analyst': {
                'trend', 'growth', 'revenue', 'profit', 'loss', 'market', 'share',
                'competition', 'strategy', 'performance', 'metrics', 'kpi', 'roi',
                'investment', 'financial', 'economic', 'business', 'analysis'
            },
            'journalist': {
                'news', 'report', 'investigation', 'source', 'evidence', 'fact',
                'statement', 'interview', 'quote', 'development', 'event', 'incident',
                'story', 'coverage', 'breaking', 'update', 'announcement'
            }
        }

        # Job-specific importance indicators
        self.job_keywords = {
            'literature_review': {
                'related work', 'previous studies', 'existing research', 'methodology',
                'findings', 'contributions', 'limitations', 'future work', 'comparison'
            },
            'exam_preparation': {
                'key concepts', 'important', 'definition', 'formula', 'example',
                'problem', 'solution', 'practice', 'review', 'summary', 'theorem'
            },
            'financial_analysis': {
                'revenue', 'profit', 'loss', 'growth', 'trend', 'performance',
                'investment', 'market', 'competition', 'strategy', 'forecast'
            }
        }

    def extract_document_content(self, pdf_path: str) -> Dict[str, Any]:
        doc = fitz.open(pdf_path)
        content = {
            'title': '',
            'sections': [],
            'full_text': '',
            'metadata': {
                'pages': len(doc),
                'filename': os.path.basename(pdf_path)
            }
        }

        all_text = []
        current_section = None

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")

            for block in blocks["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            line_text += span["text"]

                        line_text = line_text.strip()
                        if line_text:
                            all_text.append(line_text)

                            if self.is_section_heading(line_text, span.get("size", 12), span.get("flags", 0)):
                                if current_section:
                                    content['sections'].append(current_section)
                                current_section = {
                                    'title': line_text,
                                    'page': page_num + 1,
                                    'content': [],
                                    'subsections': []
                                }
                            elif current_section:
                                current_section['content'].append({
                                    'text': line_text,
                                    'page': page_num + 1
                                })

        if current_section:
            content['sections'].append(current_section)

        content['full_text'] = ' '.join(all_text)

        if content['sections']:
            content['title'] = content['sections'][0]['title']
        else:
            content['title'] = content['metadata']['filename'].replace('.pdf', '')

        doc.close()
        return content

    def is_section_heading(self, text: str, font_size: float, font_flags: int) -> bool:
        text_clean = text.strip()
        if len(text_clean) < 3 or len(text_clean) > 150:
            return False

        heading_patterns = [
            r'^\d+\.\s+',
            r'^[A-Z][A-Z\s]+$',
            r'^(Abstract|Introduction|Conclusion|References|Methods?|Results|Discussion)$',
            r'^(Chapter|Section)\s+\d+',
        ]

        for pattern in heading_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return True

        is_bold = font_flags & 2**4
        return is_bold and font_size > 11

    def calculate_section_relevance(self, section: Dict, persona: str, job: str) -> float:
        score = 0.0
        section_text = section['title'].lower()
        content_text = ' '.join([item['text'] for item in section['content']]).lower()
        full_text = section_text + ' ' + content_text

        persona_lower = persona.lower()
        relevant_keywords = set()
        for p_type, keywords in self.persona_keywords.items():
            if p_type in persona_lower:
                relevant_keywords.update(keywords)

        job_lower = job.lower()
        for job_type, keywords in self.job_keywords.items():
            if any(word in job_lower for word in job_type.split('_')):
                relevant_keywords.update(keywords)

        words = full_text.split()
        matches = sum(1 for word in words if word in relevant_keywords)
        if words:
            score += (matches / len(words)) * 10

        if any(imp in section_text for imp in ['abstract', 'introduction', 'conclusion', 'summary', 'results', 'methodology']):
            score += 2

        if len(content_text) > 500:
            score += 1
        elif len(content_text) > 200:
            score += 0.5

        return score

    def extract_subsections(self, section: Dict, persona: str, job: str) -> List[Dict]:
        subsections = []
        if not section['content']:
            return subsections

        current_text = ""
        for item in section['content']:
            text = item['text'].strip()
            sentences = re.split(r'[.!?]+', text)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20:
                    current_text += sentence + ". "
                    if len(current_text) > 300:
                        relevance_score = self.calculate_text_relevance(current_text, persona, job)
                        if relevance_score > 0.3:
                            subsections.append({
                                'document': section.get('document', ''),
                                'page_number': item['page'],
                                'refined_text': current_text.strip(),
                                'relevance_score': relevance_score
                            })
                        current_text = ""

        if current_text.strip():
            relevance_score = self.calculate_text_relevance(current_text, persona, job)
            if relevance_score > 0.3:
                subsections.append({
                    'document': section.get('document', ''),
                    'page_number': section['page'],
                    'refined_text': current_text.strip(),
                    'relevance_score': relevance_score
                })

        subsections.sort(key=lambda x: x['relevance_score'], reverse=True)
        return subsections[:5]

    def calculate_text_relevance(self, text: str, persona: str, job: str) -> float:
        text_lower = text.lower()
        relevant_keywords = set()

        persona_lower = persona.lower()
        for p_type, keywords in self.persona_keywords.items():
            if p_type in persona_lower:
                relevant_keywords.update(keywords)

        job_lower = job.lower()
        for job_type, keywords in self.job_keywords.items():
            if any(word in job_lower for word in job_type.split('_')):
                relevant_keywords.update(keywords)

        words = text_lower.split()
        if words:
            matches = sum(1 for word in words if word in relevant_keywords)
            return matches / len(words)
        return 0.0

    def analyze_documents(self, documents: List[str], persona: str, job: str) -> Dict:
        all_sections = []
        document_contents = {}

        for doc_path in documents:
            try:
                content = self.extract_document_content(doc_path)
                document_contents[doc_path] = content
                for section in content['sections']:
                    section['document'] = os.path.basename(doc_path)
                    relevance_score = self.calculate_section_relevance(section, persona, job)
                    section['importance_rank'] = relevance_score
                    all_sections.append(section)
            except Exception as e:
                print(f"Error processing {doc_path}: {str(e)}")
                continue

        all_sections.sort(key=lambda x: x['importance_rank'], reverse=True)
        top_sections = all_sections[:10]
        all_subsections = []
        for section in top_sections[:5]:
            subsections = self.extract_subsections(section, persona, job)
            all_subsections.extend(subsections)

        all_subsections.sort(key=lambda x: x['relevance_score'], reverse=True)

        return {
            "metadata": {
                "input_documents": [os.path.basename(doc) for doc in documents],
                "persona": persona,
                "job_to_be_done": job,
                "processing_timestamp": datetime.now().isoformat()
            },
            "extracted_sections": [
                {
                    "document": section['document'],
                    "page_number": section['page'],
                    "section_title": section['title'],
                    "importance_rank": round(section['importance_rank'], 3)
                }
                for section in top_sections
            ],
            "sub_section_analysis": all_subsections[:10]
        }

def main():
    input_dir = "/app/input"
    output_dir = "/app/output"
    os.makedirs(output_dir, exist_ok=True)

    config_path = os.path.join(input_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            documents = [os.path.join(input_dir, doc) for doc in config.get('documents', [])]
            persona = config.get('persona', 'Researcher')
            job = config.get('job_to_be_done', 'Analyze documents')
    else:
        documents = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
        persona = "Academic Researcher"
        job = "Analyze and extract key insights from the provided documents"

    if not documents:
        print("No PDF documents found to process")
        return

    analyzer = PersonaDrivenAnalyzer()
    try:
        print(f"Analyzing {len(documents)} documents for persona: {persona}")
        result = analyzer.analyze_documents(documents, persona, job)
        output_path = os.path.join(output_dir, "analysis_result.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Analysis complete. Results saved to {output_path}")
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        output_path = os.path.join(output_dir, "analysis_result.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": {
                    "input_documents": [os.path.basename(doc) for doc in documents],
                    "persona": persona,
                    "job_to_be_done": job,
                    "processing_timestamp": datetime.now().isoformat(),
                    "error": str(e)
                },
                "extracted_sections": [],
                "sub_section_analysis": []
            }, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
