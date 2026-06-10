from typing import Dict, List
import re

class KnowledgeExtraction:
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        return {
            'people': self._extract_people(text),
            'tools': self._extract_tools(text),
            'projects': self._extract_projects(text),
            'concepts': self._extract_concepts(text)
        }

    def extract_decisions(self, text: str) -> List[Dict]:
        decisions = []
        for sentence in text.split('.'):
            if 'decided' in sentence.lower() or 'decision' in sentence.lower():
                decisions.append({
                    'what': sentence.strip(),
                    'why': self._extract_rationale(text, sentence),
                    'when': self._extract_date(sentence),
                    'who': self._extract_decision_maker(sentence)
                })
        return decisions

    def mine_how_to_patterns(self, text: str) -> List[Dict]:
        patterns = []
        for sentence in text.split('.'):
            if 'how to' in sentence.lower() or any(verb in sentence.lower() for verb in ['first', 'then', 'finally']):
                patterns.append({
                    'pattern': sentence.strip(),
                    'steps': self._extract_steps(sentence)
                })
        return patterns

    def detect_checklists(self, text: str) -> List[str]:
        checklist_items = []
        for line in text.split('\n'):
            if line.strip().startswith(('- [ ]', '* [ ]', '☐', '□')):
                checklist_items.append(line.strip())
        return checklist_items

    def identify_best_practices(self, text: str) -> List[str]:
        best_practices = []
        keywords = ['best practice', 'recommended', 'should always', 'best way']
        for sentence in text.split('.'):
            if any(kw in sentence.lower() for kw in keywords):
                best_practices.append(sentence.strip())
        return best_practices

    def extract_lessons_learned(self, text: str) -> List[Dict]:
        lessons = []
        keywords = ['learned', 'lesson', 'mistake', 'next time']
        for sentence in text.split('.'):
            if any(kw in sentence.lower() for kw in keywords):
                lessons.append({
                    'lesson': sentence.strip(),
                    'context': self._extract_context(text, sentence)
                })
        return lessons

    def recognize_risk_patterns(self, text: str) -> List[Dict]:
        risks = []
        risk_keywords = ['risk', 'concern', 'issue', 'problem', 'blocker']
        for sentence in text.split('.'):
            if any(kw in sentence.lower() for kw in risk_keywords):
                risks.append({
                    'risk': sentence.strip(),
                    'severity': self._assess_severity(sentence)
                })
        return risks

    def identify_success_factors(self, text: str) -> List[str]:
        factors = []
        success_keywords = ['success', 'worked well', 'effective', 'achieved']
        for sentence in text.split('.'):
            if any(kw in sentence.lower() for kw in success_keywords):
                factors.append(sentence.strip())
        return factors

    def _extract_people(self, text: str) -> List[str]:
        # Extract capitalized names
        return list(set(re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', text)))

    def _extract_tools(self, text: str) -> List[str]:
        common_tools = ['Python', 'Docker', 'Kubernetes', 'AWS', 'Git', 'Jenkins']
        return [tool for tool in common_tools if tool in text]

    def _extract_projects(self, text: str) -> List[str]:
        # Extract project names (capitalized phrases)
        return list(set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Project\b', text)))

    def _extract_concepts(self, text: str) -> List[str]:
        # Extract technical terms
        return list(set(re.findall(r'\b[A-Z]{2,}\b', text)))

    def _extract_rationale(self, full_text: str, decision: str) -> str:
        # Find "because" or "since" clauses
        match = re.search(r'because|since', decision, re.IGNORECASE)
        if match:
            return decision[match.start():].strip()
        return ""

    def _extract_date(self, text: str) -> str:
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', text)
        return date_match.group(0) if date_match else ""

    def _extract_decision_maker(self, text: str) -> str:
        # Look for names before "decided"
        match = re.search(r'([A-Z][a-z]+ [A-Z][a-z]+)\s+decided', text)
        return match.group(1) if match else ""

    def _extract_steps(self, text: str) -> List[str]:
        step_keywords = ['first', 'second', 'then', 'next', 'finally']
        steps = []
        for keyword in step_keywords:
            if keyword in text.lower():
                steps.append(keyword)
        return steps

    def _extract_context(self, full_text: str, sentence: str) -> str:
        # Get surrounding sentences
        sentences = full_text.split('.')
        idx = sentences.index(sentence) if sentence in sentences else -1
        if idx > 0:
            return sentences[idx-1].strip()
        return ""

    def _assess_severity(self, text: str) -> str:
        if any(word in text.lower() for word in ['critical', 'severe', 'major']):
            return 'high'
        if any(word in text.lower() for word in ['moderate', 'medium']):
            return 'medium'
        return 'low'
