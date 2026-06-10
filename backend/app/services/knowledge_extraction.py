import re
from typing import Dict, List


def _unique(values: List[str]) -> List[str]:
    seen = set()
    unique_values = []
    for value in values:
        cleaned = value.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique_values.append(cleaned)
    return unique_values


class KnowledgeExtraction:
    decision_keywords = ("decided", "decision", "agreed", "approved", "chose", "we will")
    how_to_keywords = ("how to", "first", "second", "then", "next", "finally", "step")
    best_practice_keywords = ("best practice", "recommended", "should always", "best way", "standard practice")
    lesson_keywords = ("learned", "lesson", "mistake", "next time", "retrospective")
    risk_keywords = ("risk", "concern", "issue", "problem", "blocker", "dependency")
    success_keywords = ("success", "worked well", "effective", "achieved")

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        normalized_text = self._normalize_text(text)
        return {
            "people": self._extract_people(normalized_text),
            "tools": self._extract_tools(normalized_text),
            "projects": self._extract_projects(normalized_text),
            "concepts": self._extract_concepts(normalized_text),
        }

    def extract_decisions(self, text: str) -> List[Dict]:
        decisions = []
        for sentence in self._sentences(text):
            if self._contains(sentence, self.decision_keywords):
                decisions.append({
                    "what": sentence,
                    "why": self._extract_rationale(text, sentence),
                    "when": self._extract_date(sentence),
                    "who": self._extract_decision_maker(sentence),
                    "evidence": sentence,
                    "confidence": self._confidence(sentence, self.decision_keywords),
                })
        return self._dedupe_dicts(decisions, "what")

    def mine_how_to_patterns(self, text: str) -> List[Dict]:
        patterns = []
        for sentence in self._sentences(text):
            if self._contains(sentence, self.how_to_keywords):
                patterns.append({
                    "pattern": sentence,
                    "steps": self._extract_steps(sentence),
                    "evidence": sentence,
                    "confidence": self._confidence(sentence, self.how_to_keywords),
                })
        return self._dedupe_dicts(patterns, "pattern")

    def detect_checklists(self, text: str) -> List[str]:
        checklist_items = []
        for line in text.split("\n"):
            stripped = line.strip()
            if re.match(r"^(-|\*|\+)?\s*(\[[ xX]\]|\( \)|\(x\)|TODO:|DONE:)\s+", stripped):
                item = re.sub(r"^(-|\*|\+)?\s*(\[[ xX]\]|\( \)|\(x\)|TODO:|DONE:)\s+", "", stripped).strip()
                checklist_items.append(item)
        return _unique(checklist_items)

    def identify_best_practices(self, text: str) -> List[str]:
        best_practices = []
        for sentence in self._sentences(text):
            if self._contains(sentence, self.best_practice_keywords):
                best_practices.append(sentence)
        return _unique(best_practices)

    def extract_lessons_learned(self, text: str) -> List[Dict]:
        lessons = []
        for sentence in self._sentences(text):
            if self._contains(sentence, self.lesson_keywords):
                lessons.append({
                    "lesson": sentence,
                    "context": self._extract_context(text, sentence),
                    "evidence": sentence,
                    "confidence": self._confidence(sentence, self.lesson_keywords),
                })
        return self._dedupe_dicts(lessons, "lesson")

    def recognize_risk_patterns(self, text: str) -> List[Dict]:
        risks = []
        for sentence in self._sentences(text):
            if self._contains(sentence, self.risk_keywords):
                risks.append({
                    "risk": sentence,
                    "severity": self._assess_severity(sentence),
                    "evidence": sentence,
                    "confidence": self._confidence(sentence, self.risk_keywords),
                })
        return self._dedupe_dicts(risks, "risk")

    def identify_success_factors(self, text: str) -> List[str]:
        factors = []
        for sentence in self._sentences(text):
            if self._contains(sentence, self.success_keywords):
                factors.append(sentence)
        return _unique(factors)

    def _extract_people(self, text: str) -> List[str]:
        return _unique(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text))

    def _extract_tools(self, text: str) -> List[str]:
        common_tools = ["Python", "Docker", "Kubernetes", "AWS", "Git", "Jenkins", "Neo4j", "FastAPI", "Next.js"]
        return [tool for tool in common_tools if re.search(rf"\b{re.escape(tool)}\b", text)]

    def _extract_projects(self, text: str) -> List[str]:
        return _unique(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Project\b", text))

    def _extract_concepts(self, text: str) -> List[str]:
        return _unique(re.findall(r"\b[A-Z]{2,}\b", text))

    def _extract_rationale(self, full_text: str, decision: str) -> str:
        match = re.search(r"\b(because|since|so that|in order to)\b", decision, re.IGNORECASE)
        if match:
            return decision[match.start():].strip()
        return ""

    def _extract_date(self, text: str) -> str:
        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        return date_match.group(0) if date_match else ""

    def _extract_decision_maker(self, text: str) -> str:
        match = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+)\s+(decided|agreed|approved|chose)", text)
        return match.group(1) if match else ""

    def _extract_steps(self, text: str) -> List[str]:
        step_keywords = ["first", "second", "then", "next", "finally", "step"]
        return [keyword for keyword in step_keywords if re.search(rf"\b{keyword}\b", text, re.IGNORECASE)]

    def _extract_context(self, full_text: str, sentence: str) -> str:
        sentences = self._sentences(full_text)
        idx = sentences.index(sentence) if sentence in sentences else -1
        if idx > 0:
            return sentences[idx - 1]
        return ""

    def _assess_severity(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ["critical", "severe", "major", "blocking"]):
            return "high"
        if any(word in lowered for word in ["moderate", "medium"]):
            return "medium"
        return "low"

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("\r\n", "\n")).strip()

    def _sentences(self, text: str) -> List[str]:
        normalized = self._normalize_text(text)
        candidates = re.split(r"(?<=[.!?])\s+|\n+", normalized)
        return [candidate.strip(" -\t") for candidate in candidates if len(candidate.strip()) >= 8]

    def _contains(self, sentence: str, keywords: tuple[str, ...]) -> bool:
        lowered = sentence.lower()
        return any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in keywords)

    def _confidence(self, sentence: str, keywords: tuple[str, ...]) -> float:
        lowered = sentence.lower()
        keyword_hits = sum(1 for keyword in keywords if keyword in lowered)
        rationale_bonus = 1 if re.search(r"\b(because|since|therefore|so that|in order to)\b", lowered) else 0
        detail_bonus = 1 if len(sentence.split()) >= 8 else 0
        score = 0.55 + min(keyword_hits, 3) * 0.1 + rationale_bonus * 0.1 + detail_bonus * 0.05
        return round(min(score, 0.95), 2)

    def _dedupe_dicts(self, values: List[Dict], key: str) -> List[Dict]:
        seen = set()
        deduped = []
        for value in values:
            title = value.get(key, "").strip()
            fingerprint = re.sub(r"\W+", " ", title).strip().lower()
            if title and fingerprint not in seen:
                seen.add(fingerprint)
                deduped.append(value)
        return deduped
