
import re
from difflib import SequenceMatcher

t1 = "Yalova'da DAEŞ'e yönelik operasyonda çıkan çatışmada 3 memur şehit oldu."
t2 = "Yalova'da DEAŞ'lı teröristlerle çıkan çatışma sonucu 3 polis şehit oldu."

def temizle_original(metin):
    # Küçük harfe çevir ve sadece harfleri/sayıları al
    return set(re.sub(r'[^\w\s]', '', metin.lower()).split())

def temizle_stemmed(metin):
    # Split, lower, remove non-alphanumeric
    words = re.sub(r'[^\w\s]', '', metin.lower()).split()
    # Take first 5 chars of each word
    return set([w[:5] for w in words])

def check_jaccard(s1, s2):
    if not s1 or not s2: return 0.0
    return len(s1 & s2) / len(s1 | s2)

print(f"Original Jaccard: {check_jaccard(temizle_original(t1), temizle_original(t2))}")
print(f"Stemmed Jaccard: {check_jaccard(temizle_stemmed(t1), temizle_stemmed(t2))}")

seq_ratio = SequenceMatcher(None, t1, t2).ratio()
print(f"SequenceMatcher Ratio: {seq_ratio}")
