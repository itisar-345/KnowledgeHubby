from typing import Dict, List, Any

class CurationLayer:
    def __init__(self):
        self.playbooks = {}
        self.templates = {}

    def build_playbook(self, title: str, steps: List[Dict]) -> Dict:
        playbook_id = f"playbook_{len(self.playbooks)}"
        playbook = {
            'id': playbook_id,
            'title': title,
            'steps': steps,
            'category': self._categorize_playbook(title)
        }
        self.playbooks[playbook_id] = playbook
        return playbook

    def create_onboarding_path(self, role: str, topics: List[str]) -> Dict:
        return {
            'role': role,
            'path': [
                {'topic': topic, 'order': i, 'resources': self._find_resources(topic)}
                for i, topic in enumerate(topics)
            ]
        }

    def generate_faq(self, questions: List[str], knowledge_base: Dict) -> List[Dict]:
        faq = []
        for question in questions:
            answer = self._find_answer(question, knowledge_base)
            faq.append({'question': question, 'answer': answer})
        return faq

    def manage_template_library(self, template: Dict) -> str:
        template_id = f"template_{len(self.templates)}"
        self.templates[template_id] = template
        return template_id

    def create_best_practice_repo(self, practices: List[Dict]) -> Dict:
        return {
            'practices': practices,
            'categories': self._categorize_practices(practices),
            'searchable': True
        }

    def compile_checklist(self, task_type: str, items: List[str]) -> Dict:
        return {
            'task_type': task_type,
            'items': [{'item': item, 'checked': False} for item in items],
            'completion': 0
        }

    def generate_process_doc(self, process_name: str, steps: List[Dict]) -> str:
        doc = f"# {process_name}\n\n"
        for i, step in enumerate(steps, 1):
            doc += f"{i}. {step.get('description', '')}\n"
            if step.get('substeps'):
                for substep in step['substeps']:
                    doc += f"   - {substep}\n"
        return doc

    def identify_knowledge_gaps(self, topics: List[str], knowledge_base: Dict) -> List[str]:
        gaps = []
        for topic in topics:
            if not self._has_coverage(topic, knowledge_base):
                gaps.append(topic)
        return gaps

    def get_playbook(self, playbook_id: str) -> Dict:
        return self.playbooks.get(playbook_id)

    def search_templates(self, query: str) -> List[Dict]:
        results = []
        for template_id, template in self.templates.items():
            if query.lower() in template.get('title', '').lower():
                results.append(template)
        return results

    def _categorize_playbook(self, title: str) -> str:
        categories = {
            'event': ['event', 'planning', 'conference'],
            'lab': ['lab', 'protocol', 'experiment'],
            'onboarding': ['onboarding', 'training', 'new hire']
        }
        for category, keywords in categories.items():
            if any(kw in title.lower() for kw in keywords):
                return category
        return 'general'

    def _find_resources(self, topic: str) -> List[str]:
        # Placeholder for resource finding
        return [f"Resource about {topic}"]

    def _find_answer(self, question: str, knowledge_base: Dict) -> str:
        # Simple keyword matching
        for doc in knowledge_base.get('documents', []):
            if any(word in doc.get('content', '').lower() for word in question.lower().split()):
                return doc.get('content', '')[:200]
        return "Answer not found"

    def _categorize_practices(self, practices: List[Dict]) -> Dict[str, List[Dict]]:
        categories = {}
        for practice in practices:
            category = practice.get('category', 'general')
            if category not in categories:
                categories[category] = []
            categories[category].append(practice)
        return categories

    def _has_coverage(self, topic: str, knowledge_base: Dict) -> bool:
        for doc in knowledge_base.get('documents', []):
            if topic.lower() in doc.get('content', '').lower():
                return True
        return False
