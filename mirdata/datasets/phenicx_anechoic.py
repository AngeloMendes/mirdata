# -*- coding: utf-8 -*-
"""PHENICX-Anechoic Dataset Loader

This dataset includes audio and annotations useful for tasks as score-informed source separation, score following, multi-pitch estimation, transcription or instrument detection, in the context of symphonic music:
M. Miron, J. Carabias-Orti, J. J. Bosch, E. Gómez and J. Janer, "Score-informed source separation for multi-channel orchestral recordings", Journal of Electrical and Computer Engineering (2016))"

We do not provide the original audio files, which can be found at the web page hosted by Aalto University. However, with their permission we distribute the denoised versions for some of the anechoic orchestral recordings. The original dataset was introduced in:
Pätynen, J., Pulkki, V., and Lokki, T., "Anechoic recording system for symphony orchestra," Acta Acustica united with Acustica, vol. 94, nr. 6, pp. 856-865, November/December 2008.

Additionally, we provide the associated musical note onset and offset annotations, and the Roomsim configuration files used to generate the multi-microphone recordings.

The original anechoic dataset in Pätynen et al. consists of four passages of symphonic music from the Classical and Romantic periods. This work presented a set of anechoic recordings for each of the instruments, which were then synchronized between them so that they could later be combined to a mix of the orchestra. In order to keep the evaluation setup consistent between the four pieces, we selected the following instruments: violin, viola, cello, double bass, oboe, flute, clarinet, horn, trumpet and bassoon. A list of the characteristics of the four pieces can be found below:

Mozart
- duration: 3min 47s
- period: classical
- no. sources: 8
- total no. instruments: 10
- max. instruments/source: 2

Beethoven
- duration: 3min 11s
- period: classical
- no. sources: 10
- total no. instruments: 20
- max. instruments/source: 4

Beethoven
- duration: 2min 12s
- period: romantic
- no. sources: 10
- total no. instruments: 30
- max. instruments/source: 4

Bruckner
- duration: 1min 27s
- period: romantic
- no. sources: 10
- total no. instruments: 39
- max. instruments/source: 12

For more details, please visit: https://www.upf.edu/web/mtg/phenicx-anechoic

"""

import glob
import librosa
import logging
import numpy as np
import os
import re

from mirdata import download_utils
from mirdata import jams_utils
from mirdata import core
from mirdata import utils

BIBTEX = """
@article{miron2016score,
  title={Score-informed source separation for multichannel orchestral recordings},
  author={Miron, Marius and Carabias-Orti, Julio J and Bosch, Juan J and G{\'o}mez, Emilia and Janer, Jordi},
  journal={Journal of Electrical and Computer Engineering},
  volume={2016},
  year={2016},
  publisher={Hindawi}
}
@article{patynen2008anechoic,
  title={Anechoic recording system for symphony orchestra},
  author={P{\"a}tynen, Jukka and Pulkki, Ville and Lokki, Tapio},
  journal={Acta Acustica united with Acustica},
  volume={94},
  number={6},
  pages={856--865},
  year={2008},
  publisher={S. Hirzel Verlag}
}
"""

REMOTES = {
    'all': download_utils.RemoteFileMetadata(
        filename='PHENICX-Anechoic.zip',
        url='https://zenodo.org/record/840025/files/PHENICX-Anechoic.zip?download=1',
        checksum='7fec47568263476ecac0103aef608629',
        destination_dir='..',
    )
}

DATA = utils.LargeData('phenicx_anechoic_index.json')

DATASET_SECTIONS = {
    'doublebass': 'strings',
    'cello': 'strings',
    'clarinet': 'woodwinds',
    'viola': 'strings',
    'violin': 'strings',
    'oboe': 'woodwinds',
    'flute': 'woodwinds',
    'trumpet': 'brass',
    'bassoon': 'woodwinds',
    'horn': 'brass',
}

class Track(core.Track):
    """Phenicx-Anechoic Track class

    Args:
        track_id (str): track id of the track

    Attributes:
        audio_path (list(str)): path to the audio files
        notes_path (list(str)): path to the audio files
        notes_original_path (list(str)): path to the audio files
        instrument (str): the name of the instrument
        piece (str): the name of the piece
        n_voices (int): the number of voices in this instrument
        track_id (str): track id

    Cached Properties:
        melody (F0Data): melody annotation

    """

    def __init__(
        self,
        track_id,
        data_home,
        dataset_name,
        index,
        metadata,
    ):
        super().__init__(
            track_id,
            data_home,
            dataset_name,
            index,
            metadata,
        )

        self.instrument = self.track_id.split('-')[1]
        self.piece = self.track_id.split('-')[0]

        self.audio_paths = [os.path.join(
            self._data_home, self._track_paths[key][0]
        ) for key in self._track_paths if 'audio_' in key]

        self.n_voices = len(self.audio_paths)

        self.notes_path = os.path.join(
            self._data_home, self._track_paths['notes'][0]
        )

        self.notes_original_path = os.path.join(
            self._data_home, self._track_paths['notes_original'][0]
        )

    @property
    def audio(self) -> Optional[Tuple[np.ndarray, float]]:
        """the track's audio (mono)

        Returns:
            * np.ndarray - the mono audio signal
            * float - The sample rate of the audio file

        """
        audio_mix,sr = load_audio(self.audio_paths[0])
        for i in range(1,self.n_voices):
            audio,_ = load_audio(self.audio_paths[i])
            audio_mix += audio
        return audio_mix,sr

    def get_audio_voice(self,id_voice) -> Optional[Tuple[np.ndarray, float]]:
        """the track's audio (mono)

        Returns:
            * np.ndarray - the mono audio signal
            * float - The sample rate of the audio file

        """
        return load_audio(self.audio_paths[id_voice])

    def to_jams(self):
        """Get the track's data in jams format

        Returns:
            jams.JAMS: the track's data in jams format

        """
        return jams_utils.jams_converter(
            audio_path=self.audio_paths[0]
        )



class MultiTrack(core.MultiTrack):
    """Phenicx-Anechoic MultiTrack class

    Args:
        mtrack_id (str): track id of the track
        data_home (str): Local path where the dataset is stored.
            If `None`, looks for the data in the default directory, `~/mir_datasets/Phenicx-Anechoic`


    Attributes:
        audio_path (str): path to the audio files associated with this track
        annotation_path (str): path to the annotations files associated with this track
        track_id (str): track id
        instruments (list): list of strings with instrument names
        sections (list): list of strings with section names
    """

    def __init__(self, mtrack_id, data_home=None):
        if mtrack_id not in DATA.index['multitracks']:
            raise ValueError('{} is not a valid track ID in Example'.format(mtrack_id))

        self.mtrack_id = mtrack_id

        self._data_home = data_home

        self.mtrack_ids = [k for k, v in sorted(DATA.index['multitracks'][mtrack_id]['tracks'].items())]
        self.tracks = {k:Track(self.mtrack_id, k, self._data_home) for k, v in sorted(DATA.index['multitracks'][mtrack_id]['tracks'].items())}

        self.track_audio_property = "audio" # the attribute of Track which returns the relevant audio file for mixing

        self._metadata = None

        #### parse the keys for the list of instruments
        self.instruments = sorted(
            [
                source.replace('score-', '')
                for source in DATA.index['multitracks'][mtrack_id].keys()
                if 'score-' in source
            ]
        )

        #### get the corresponding sections for the instruments
        self.sections = sorted(
            list(
                set(
                    section
                    for instrument, section in DATASET_SECTIONS.items()
                    if instrument in self.instruments
                )
            )
        )



    @property
    def audio_mix(self):
        """np.ndarray(n_channels, n_samples): audio signal"""
        return self.get_audio_mix_instruments(self.instruments, weights=None, average=True, enforce_length=False)


    @caches_property
    def scores(self):
        """list(EventData): list of musical score as EventData for all instruments"""
        return [self.get_score_mix_instruments(instrument) for instrument in self.instruments]


    def get_trackids(self,instruments):
        """Get the track_ids for the given instrument(s)
        Args:
            instruments (list or string): list of instrument names

        Returns:
           (list): list of track_ids

        """
        if isinstance(instruments, str):
            instruments = [instruments]
        assert isinstance(instruments, list)
        assert all(elem in self.instruments for elem in instruments),'The instruments {} must be: {}'.format(instruments,self.instruments)

        return [tid for tid in self.mtrack_ids if re.compile('|'.join(instruments),re.IGNORECASE).search(tid)]


    def get_audio_mix_instruments(self, instruments, weights=None, average=True, enforce_length=True):
        """Get the audio mix/linear sum for the given instrument(s)
        Args:
            instruments (list or string): list of instrument names

        Returns:
           np.ndarray(n_channels, n_samples): mixed audio

        """
        return self.get_target(self.get_trackids(instruments), weights=weights, average=average, enforce_length=enforce_length)


    def get_audio_instruments(self, instruments, weights=None, average=True, enforce_length=True):
        """Get the audios for the given instrument(s)
        Args:
            instruments (list or string): list of instrument names

        Returns:
           list(np.ndarray(n_channels, n_samples,n_instruments)): list of audio signals for the instruments

        """
        if isinstance(instruments, str):
            instruments = [instruments]
        return np.stack([self.get_audio_mix_instruments(instrument, weights=weights, average=average, enforce_length=True) for instrument in instruments],axis=-1)


    def get_audio_sections(self, sections, weights=None, average=True):
        """Get the audios for the given section(s)
        Args:
            sections (list or string): list of section names

        Returns:
           list(np.ndarray(n_channels, n_samples, n_instruments)): list of audio signals for the sections

        """
        if isinstance(sections, str):
            sections = [sections]
        instruments_for_sections = [[k for k,s in DATASET_SECTIONS.items() if s == section] for section in sections]
        return np.stack([self.get_audio_mix_instruments(instruments, weights=weights, average=average, enforce_length=True) for instruments in instruments_for_sections],axis=-1)


    def get_score_mix_instruments(self, instruments):
        """Get the mixed score for the instrument(s)
        Args:
            instruments (list or string)): list of instrument names to get the score for

        Returns:
            score (EventData): EventData tuples (start_times, end_times, note)

        """
        if isinstance(instruments, str):
            instruments = [instruments]
        assert isinstance(instruments, list)
        assert all(elem in self.instruments for elem in instruments),'The instruments {} must be: {}'.format(instruments,self.instruments)

        score_paths = [v[0] for k,v in DATA.index['multitracks'][self.mtrack_id].items() if 'score-' in k and re.compile('|'.join(instruments),re.IGNORECASE).search(v[0])]

        start_times = []
        end_times = []
        score = []
        for path in score_paths:
            full_path = os.path.join(self._data_home,path)
            if not os.path.exists(full_path):
                raise IOError("path {} does not exist".format(full_path))

            #### read start, end times
            times = np.loadtxt(full_path, delimiter=",", usecols=[0, 1], dtype=np.float)
            start_times.append(times[:, 0])
            end_times.append(times[:, 1])

            #### read notes as string
            with open(full_path) as f:
                content = f.readlines()
                sc = np.array([line.split(',')[2].strip('\n') for line in content])
                score.append(sc)

        start_times = np.concatenate(start_times)
        end_times = np.concatenate(end_times)
        score = np.concatenate(score)

        #### sort on the start time
        ind = np.argsort(start_times, axis=0)
        start_times = np.take_along_axis(start_times, ind, axis=0)
        end_times = np.take_along_axis(end_times, ind, axis=0)
        score = np.take_along_axis(score, ind, axis=0)

        data = utils.EventData(start_times, end_times, score)
        return data


    def to_jams(self):
        """Jams: the track's data in jams format"""

        metadata = {}
        metadata['instruments'] = self.instruments
        metadata['sections'] = self.sections

        audio_paths = [
            track.audio_path
            for k,track in self.tracks.items()
        ]

        score_data = [
            (self.get_score_instruments(instrument), 'score-' + instrument) for instrument in self.instruments
        ]

        return jams_utils.jams_converter(
            audio_path=audio_paths[0],
            event_data=score_data,
            metadata=metadata
        )

@io.coerce_to_bytes_io
def load_audio(fhandle: BinaryIO) -> Tuple[np.ndarray, float]:
    """Load an Orchset audio file.

    Args:
        fhandle (str or file-like): File-like object or path to audio file

    Returns:
        * np.ndarray - the mono audio signal
        * float - The sample rate of the audio file

    """
    if not os.path.exists(audio_path):
        raise IOError("audio_path {} does not exist".format(audio_path))
    return librosa.load(audio_path, sr=None, mono=True)


# def download(data_home=None, force_overwrite=False, cleanup=True):
#     """Download the dataset.

#     Args:
#         data_home (str):
#             Local path where the dataset is stored.
#             If `None`, looks for the data in the default directory, `~/mir_datasets`
#         force_overwrite (bool):
#             Whether to overwrite the existing downloaded data
#         cleanup (bool):
#             Whether to delete the zip/tar file after extracting.

#     """
#     if data_home is None:
#         data_home = utils.get_default_dataset_path(DATASET_DIR)

#     download_utils.downloader(
#         data_home,
#         remotes=REMOTES,
#         info_message=None,
#         force_overwrite=force_overwrite,
#         cleanup=cleanup,
#     )

# def validate(data_home=None, silence=False):
#     """Validate if the stored dataset is a valid version

#     Args:
#         data_home (str): Local path where the dataset is stored.
#             If `None`, looks for the data in the default directory, `~/mir_datasets`
#     Returns:
#         missing_files (list): List of file paths that are in the dataset index
#             but missing locally
#         invalid_checksums (list): List of file paths that file exists in the dataset
#             index but has a different checksum compare to the reference checksum
#     """
#     if data_home is None:
#         data_home = utils.get_default_dataset_path(DATASET_DIR)

#     missing_files, invalid_checksums = utils.validator(
#         DATA.index, data_home, silence=silence
#     )
#     return missing_files, invalid_checksums



# def track_ids():
#     """Return track ids

#     Returns:
#         (list): A list of track ids
#     """
#     return list(DATA.index.keys())


# def load(data_home=None):
#     """Load  dataset
#     Args:
#         data_home (str): Local path where the dataset is stored.
#             If `None`, looks for the data in the default directory, `~/mir_datasets`
#     Returns:
#         (dict): {`track_id`: track data}
#     """
#     if data_home is None:
#         data_home = utils.get_default_dataset_path(DATASET_DIR)

#     data = {}
#     for key in DATA.index.keys():
#         data[key] = MultiTrack(key, data_home=data_home)
#     return data


# def cite():
#     """Print the reference"""

#     cite_data = """
# =========== MLA ===========
# Miron, Marius, et al. "Score-informed source separation for multichannel orchestral recordings." Journal of Electrical and Computer Engineering 2016 (2016).

# Pätynen, Jukka, Ville Pulkki, and Tapio Lokki. "Anechoic recording system for symphony orchestra." Acta Acustica united with Acustica 94.6 (2008): 856-865.
# ========== Bibtex ==========
# @article{miron2016score,
#   title={Score-informed source separation for multichannel orchestral recordings},
#   author={Miron, Marius and Carabias-Orti, Julio J and Bosch, Juan J and G{\'o}mez, Emilia and Janer, Jordi},
#   journal={Journal of Electrical and Computer Engineering},
#   volume={2016},
#   year={2016},
#   publisher={Hindawi}
# }

# @article{patynen2008anechoic,
#   title={Anechoic recording system for symphony orchestra},
#   author={P{\"a}tynen, Jukka and Pulkki, Ville and Lokki, Tapio},
#   journal={Acta Acustica united with Acustica},
#   volume={94},
#   number={6},
#   pages={856--865},
#   year={2008},
#   publisher={S. Hirzel Verlag}
# }

# """
#     print(cite_data)


# ##########################################
# #### derived from musdb multi-track code
# #### distributed under MIT license
# ##########################################


# class Source(object):
#     """An audio Target which is a linear mixture of several sources

#     Args:
#         name (str): Name of this source
#         stem_id (int): stem/substream ID is set here.
#         path (str): Absolute path to audio file
#         gain (float): Mixing weight for this source
#     """

#     def __init__(
#         self,
#         name=None,  # has its own name
#         path=None,  # might have its own path
#         stem_id=None,  # might have its own stem_id
#         gain=1.0,
#         *args,
#         **kwargs,
#     ):
#         self.name = name
#         self.path = path
#         self.stem_id = stem_id
#         self.gain = gain
#         self._audio = None

#     def __repr__(self):
#         return self.path

#     @property
#     def audio(self):
#         # return cached audio if explicitly set by setter
#         if self._audio is not None:
#             return self._audio
#         # read from disk to save RAM otherwise
#         else:
#             audio, self._rate = load_audio(self.path)
#             self.shape = audio.shape
#             return audio

#     @audio.setter
#     def audio(self, array):
#         self._audio = array

#     @property
#     def rate(self):
#         return self._rate

#     def __eq__(self, other):
#         """ tests if two sources are equal
#         """
#         if not isinstance(other, Source):
#             return False
#         else:
#             return (
#                 self.name == other.name
#                 and self.gain == other.gain
#                 and os.path.basename(self.path) == os.path.basename(other.path)
#             )


# # Target from musdb DB mixed from several sources
# class Target(object):
#     """
#     An audio Target which is a linear mixture of several sources/targets
#     Attributes

#     Args:
#         sources (list[Source/Target]): list of ``Source`` objects for this ``Target``
#     """

#     def __init__(
#         self,
#         sources,  # list of Source objects
#         instruments,  # list of str (instruments)
#         score_path,  # paths to score/annotation files
#         name=None,  # has its own name
#     ):
#         assert isinstance(sources, list), "sources should be a list of Source objects"
#         assert isinstance(
#             instruments, list
#         ), "instruments should be a list of str representing instruments"
#         self.sources = sources
#         self.name = name
#         self.score_path = score_path
#         self.instruments = sorted(instruments)

#     @property
#     def audio(self):
#         """array_like: [shape=(num_samples)]
#         mixes audio for targets on the fly
#         """
#         for i, source in enumerate(self.sources):
#             audio = source.audio
#             sr = source.rate
#             if audio is not None:
#                 if i == 0:
#                     mix = source.gain * audio
#                     self._rate = sr
#                 else:
#                     assert (
#                         sr == self.rate
#                     ), "the sampling rate is different for two sources of the same target"
#                     if len(audio) > len(mix):
#                         prev_len = len(mix)
#                         mix = np.resize(mix, audio.shape)
#                         mix[prev_len:] = 0.0
#                         mix += source.gain * audio
#                     elif len(audio) < len(mix):
#                         mix[: len(audio)] += source.gain * audio
#                     else:
#                         mix += source.gain * audio
#         return mix

#     @property
#     def rate(self):
#         return self._rate

#     @utils.cached_property
#     def score(self):
#         """ returns the score
#         """
#         if not os.path.isdir(self.score_path):
#             raise IOError("path {} does not exist".format(self.score_path))
#         score_paths = [
#             os.path.join(self.score_path, instrument + '.txt')
#             for instrument in self.instruments
#         ]
#         return load_score(score_paths)

#     @utils.cached_property
#     def original_score(self):
#         """ returns the original score
#         """
#         if not os.path.isdir(self.score_path):
#             raise IOError("path {} does not exist".format(self.score_path))
#         score_paths = [
#             os.path.join(self.score_path, instrument + '_o.txt')
#             for instrument in self.instruments
#         ]
#         return load_score(score_paths)

#     def __repr__(self):
#         parts = []
#         for source in self.sources:
#             parts.append(source.name)
#         return '+'.join(parts)

#     def __eq__(self, other):
#         """ tests if two targets are equal
#         """
#         if not isinstance(other, Target):
#             print('not the same type')
#             return False
#         else:
#             if self.name != other.name:
#                 print('names not equal')
#                 return False
#             if self.instruments != other.instruments:
#                 print('instruments not equal')
#                 return False
#             for s1, s2 in zip(self.sources, other.sources):
#                 if s1 != s2:
#                     return False
#             return True