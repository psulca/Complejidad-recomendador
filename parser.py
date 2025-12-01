import re
from typing import List, Tuple, Union


def parse_requisitos(req_str: str) -> List[Tuple[str, ...]]:
    s = str(req_str).strip()
    if not s or s == "nan":
        return []
    
    parts = re.split(r'(?:,|;|/|\s+y\s+|\s+o\s+)', s, flags=re.IGNORECASE)
    parsed = []
    
    for t in parts:
        t = t.strip()
        if not t:
            continue
        
        U = t.upper()
        
        m_cc = re.fullmatch(r'([A-Z]{2,}\d{2,})\s*:\s*(\d+)', U)
        if m_cc:
            parsed.append(("COURSE_CRED", m_cc.group(1), int(m_cc.group(2))))
            continue
        
        m_cr = re.search(r'(\d+)\s*(CRED|CREDITOS?)', U)
        if m_cr:
            parsed.append(("CRED", int(m_cr.group(1))))
            continue
        
        if re.fullmatch(r'[A-Z]{2,}\d{2,}', U):
            parsed.append(("COURSE", U))
    
    return parsed

