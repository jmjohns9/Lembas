# Stand-in for tiktoken: counts with Anthropic's published Claude tokenizer
# (bundled in the litellm wheel), since the o200k download is blocked here.
import os
from tokenizers import Tokenizer
_tok = Tokenizer.from_file(os.path.join(os.path.dirname(__file__), "claude_tokenizer.json"))
class _Enc:
    def encode(self, text):
        return _tok.encode(text).ids
def get_encoding(name):
    return _Enc()
