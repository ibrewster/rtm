from obspy.clients.fdsn import Client as FDSN_Client
from obspy.clients.earthworm import Client as EW_Client
from obspy.clients.fdsn.header import FDSNException
from obspy import Stream


# Define IRIS and AVO clients (define WATC client within function)
iris_client = FDSN_Client('IRIS')
avo_client = EW_Client('pubavo1.wr.usgs.gov', port=16023)  # 16023 is long-term


def gather_waveforms(source, network, station, starttime, endtime,
                     watc_username=None, watc_password=None):
    """
    Gather infrasound waveforms from IRIS or WATC FDSN, or AVO Winston, and
    output a Stream object.

    Args:
        source: Which source to gather waveforms from - options are:
                'IRIS' <-- IRIS FDSN
                'WATC' <-- WATC FDSN
                'AVO'  <-- AVO Winston
        network: SEED network code
        station: SEED station code
        starttime: Start time for data request (UTCDateTime)
        endtime: End time for data request (UTCDateTime)
        watc_username: Username for WATC FDSN server
        watc_password: Password for WATC FDSN server
    Returns:
        st_out: Stream containing gathered waveforms
    """

    # IRIS FDSN
    if source == 'IRIS':

        print('Reading data from IRIS FDSN.')
        st_out = iris_client.get_waveforms(network, station, '*', 'BDF,HDF',
                                           starttime, endtime)

    # WATC FDSN
    elif source == 'WATC':

        print('Connecting to WATC FDSN...')
        try:
            watc_client = FDSN_Client('http://10.30.5.10:8080',
                                      user=watc_username,
                                      password=watc_password)
        except FDSNException:
            print('...issue connecting to WATC FDSN. Check your VPN '
                  'connection and try again.')
            return

        print('...successfully connected. Reading data from WATC FDSN.')
        st_out = watc_client.get_waveforms(network, station, '*', 'BDF,HDF',
                                           starttime, endtime)

    # AVO Winston
    elif source == 'AVO':

        print('Reading data from AVO Winston.')

        # Array case
        if station in ['ADKI', 'AKS', 'DLL', 'OKIF', 'SDPI']:

            # Select the correct channel
            if station in ['DLL', 'OKIF']:
                channel = 'HDF'
            else:
                channel = 'BDF'

            st_out = Stream()  # Make an empty Stream object to populate

            # Deal with funky channel naming convention for AKS (for all other
            # arrays, six elements are assumed)
            if station == 'AKS':
                for channel in ['BDF', 'BDG', 'BDH', 'BDI']:
                    st_out += avo_client.get_waveforms(network, station, '',
                                                       channel, starttime,
                                                       endtime)
            else:
                for location in ['01', '02', '03', '04', '05', '06']:
                    st_out += avo_client.get_waveforms(network, station,
                                                       location, channel,
                                                       starttime, endtime)

        # Single station case
        else:
            st_out = avo_client.get_waveforms(network, station, '', 'BDF',
                                              starttime, endtime)

    else:

        print('Unrecognized source. Valid options are \'IRIS\', \'WATC\', or '
              '\'AVO\'.')
        return

    st_out.sort()

    return st_out
