class Ema:
    '''Exponential moving average (EMA)'''

    def __init__(self, half_life):
        self.a = 0.5 ** (1 / half_life)
        self.__value = None
        self.__samples_needed = half_life

    @property
    def value(self):
        return self.__value

    def step(self, value):
        if self.__value is None:
            self.__value = value
        self.__value = self.a * self.__value + (1-self.a) * value
        self.__samples_needed = max(0, self.__samples_needed - 1)

    @property
    def ready(self):
        return self.__samples_needed == 0
