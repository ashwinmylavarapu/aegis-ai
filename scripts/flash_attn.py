def __getattr__(name): raise ImportError('flash_attn not available on MPS')
