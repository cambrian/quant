import pandas as pd


# TODO: actually convert quotes, not just volume
# think about how to do this. what if a quote_usd pair does not exist on a :particular exchange?
def convert_quotes_to_usd(frame):
    frame = frame.copy()
    # .values call necessary because assigning to indexslices is buggy
    # see https://github.com/pandas-dev/pandas/issues/10440
    frame.loc[pd.IndexSlice[:, "volume"]] = (
        frame.xs("volume", level=1) * frame.xs("price", level=1)
    ).values
    return frame


class UsdConverter:
    """
    Converts non-usd quotes to USD, and back. Also converts volumes.
    """

    def __init__(self):
        self.current_frame = None

    def step(self, frame):
        self.current_frame = frame
        frame = convert_quotes_to_usd(frame)
        return frame

    def unconvert(self, usd_prices):
        pass
