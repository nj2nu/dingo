import numpy as np
from gwpy.timeseries import TimeSeries
import pycbc.psd

from dingo.gw.gwutils import get_window


def download_psd(det, time_start, time_psd, window, f_s):
    """
    Download strain data and generate a PSD based on these. Use num_segments of length
    time_segment, starting at GPS time time_start.

    Parameters
    ----------
    det: str
        detector
    time_start: float
        start GPS time for PSD estimation
    time_psd: float = 1024
        time in seconds for strain used for PSD generation
    window: Union(np.ndarray, dict)
        Window used for PSD generation, needs to be the same as used for Fourier
        transform of event strain data.
        Provided as dict, window is generated by window = dingo.gw.gwutils.get_window(
        **window).
    f_s: float
        sampling rate of strain data

    Returns
    -------
    psd: np.array
        array of psd
    """
    # download strain data for psd
    # print("Downloading strain data for PSD estimation.", end=" ")
    time_end = time_start + time_psd
    psd_strain = TimeSeries.fetch_open_data(
        det, time_start, time_end, sample_rate=f_s, cache=True
    )
    # print("Done.")
    psd_strain = psd_strain.to_pycbc()

    # generate window
    window = get_window(window)

    # generate PSD from strain data
    psd = pycbc.psd.estimate.welch(
        psd_strain,
        seg_len=len(window),
        seg_stride=len(window),
        window=window,
        avg_method="median",
    )

    return np.array(psd)


def download_raw_data(
    time_event, time_segment, time_psd, time_buffer, detectors, window, f_s
):
    # parse settings
    # time_segment = settings["window"]["T"]  # for now; change later for non-FD data
    # time_psd = settings["time_psd"]
    # time_buffer = settings["time_buffer"]
    # detectors = settings["detectors"]
    # window = settings["window"]

    data = {"strain": {}, "psd": {}}

    for det in detectors:
        data["strain"][det] = TimeSeries.fetch_open_data(
            det,
            time_event + time_buffer - time_segment,
            time_event + time_buffer,
            sample_rate=f_s,
            cache=True,
        )
        data["psd"][det] = download_psd(
            det,
            time_start=time_event + time_buffer - time_psd - time_segment,
            time_psd=time_psd,
            window=window,
            f_s=f_s,
        )

    return data
