class _LazyAnimation:
    def __init__(self, kind, empty):
        self._kind = kind
        self._empty = empty
        self._value = None

    def _get(self):
        if self._value is None:
            self._value = _animation_fetch(self._kind) or self._empty
        return self._value

    def invalidate(self):
        self._value = None

    def __len__(self):
        return len(self._get())

    def __iter__(self):
        return iter(self._get())

    def __getitem__(self, key):
        return self._get()[key]

    def __bool__(self):
        return bool(self._get())

    def __contains__(self, key):
        return key in self._get()

    def keys(self):
        return self._get().keys()

    def get(self, key, default=None):
        return self._get().get(key, default)

    def __repr__(self):
        return repr(self._get())

