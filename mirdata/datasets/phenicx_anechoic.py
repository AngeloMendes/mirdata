"""PHENICX-Anechoic Dataset Loader

.. admonition:: Dataset Info
    :class: dropdown

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
import logging
import os, glob, re
import jams
import librosa
import numpy as np
from typing import BinaryIO, Optional, TextIO, Tuple

from mirdata import download_utils
from mirdata import jams_utils
from mirdata import core
from mirdata import annotations
from mirdata import io


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
    "all": download_utils.RemoteFileMetadata(
        filename="PHENICX-Anechoic.zip",
        url="https://zenodo.org/record/840025/files/PHENICX-Anechoic.zip?download=1",
        checksum="7fec47568263476ecac0103aef608629",
        destination_dir="..",
        # unpack_directories=["PHENICX-Anechoic"]
    )
}

LICENSE_INFO = """
Creative Commons Attribution Non Commercial Share Alike 4.0 International
"""

DATASET_SECTIONS = {
    "doublebass": "strings",
    "cello": "strings",
    "clarinet": "woodwinds",
    "viola": "strings",
    "violin": "strings",
    "oboe": "woodwinds",
    "flute": "woodwinds",
    "trumpet": "brass",
    "bassoon": "woodwinds",
    "horn": "brass",
}


class Track(core.Track):
    """Phenicx-Anechoic Track class

    Args:
        track_id (str): track id of the track

    Attributes:
        audio_path (list): path to the audio files
        notes_path (list): path to the audio files
        notes_original_path (list): path to the audio files
        instrument (str): the name of the instrument
        piece (str): the name of the piece
        n_voices (int): the number of voices in this instrument
        track_id (str): track id

    Cached Properties:
        melody (F0Data): melody annotation

    """

    def __init__(
        self, track_id, data_home, dataset_name, index, metadata,
    ):
        super().__init__(
            track_id, data_home, dataset_name, index, metadata,
        )

        self.instrument = self.track_id.split("-")[1]
        self.piece = self.track_id.split("-")[0]

        self.audio_paths = [
            os.path.join(self._data_home, self._track_paths[key][0])
            for key in self._track_paths
            if "audio_" in key
        ]

        self.n_voices = len(self.audio_paths)

        self.notes_path = os.path.join(self._data_home, self._track_paths["notes"][0])

        self.notes_original_path = os.path.join(
            self._data_home, self._track_paths["notes_original"][0]
        )

    @property
    def audio(self) -> Optional[Tuple[np.ndarray, float]]:
        """the track's audio

        Returns:
            * np.ndarray - the mono audio signal
            * float - The sample rate of the audio file

        """
        audio_mix, sr = load_audio(self.audio_paths[0])

        for i in range(1, self.n_voices):
            audio, _ = load_audio(self.audio_paths[i])
            audio_mix += audio
        return audio_mix, sr

    @core.cached_property
    def notes(self) -> Optional[annotations.NoteData]:
        """the track's notes corresponding to the score aligned to the audio

        Returns:
            NoteData: Note data for the track

        """
        return load_score(self.notes_path)

    @core.cached_property
    def notes_original(self) -> Optional[annotations.NoteData]:
        """the track's notes corresponding to the original score

        Returns:
            NoteData: Note data for the track

        """
        return load_score(self.notes_original_path)

    def get_audio_voice(self, id_voice: int) -> Optional[Tuple[np.ndarray, float]]:
        """the track's audio

        Returns:
            * np.ndarray - the mono audio signal
            * float - The sample rate of the audio file

        """
        assert id_voice < self.n_voices
        return load_audio(self.audio_paths[id_voice])

    def to_jams(self):
        """Get the track's data in jams format

        Returns:
            jams.JAMS: the track's data in jams format

        """
        return jams_utils.jams_converter(
            audio_path=self.audio_paths[0], note_data=[(self.notes, "aligned notes")]
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
        mtrack_id (str): multitrack id
        tracks (list): list of track ids within this multitrack
    """

    def __init__(
        self,
        mtrack_id,
        data_home,
        dataset_name,
        index,
        track_class=Track,
        metadata=None,
    ):
        super().__init__(
            mtrack_id, data_home, dataset_name, index, Track, metadata,
        )

        #### parse the keys for the dictionary of instruments and strings
        self.instruments = {
            source.replace(self.mtrack_id + "-", ""): source
            for source in self.track_ids
        }
        self.sections = {"brass": [], "strings": [], "woodwinds": []}
        for instrument, track_id in self.instruments.items():
            self.sections[DATASET_SECTIONS[instrument]].append(track_id)

        self.piece = self.mtrack_id

    @property
    def track_audio_property(self):
        #### the attribute of Track which returns the relevant audio file for mixing
        return "audio"

    def get_audio_for_instrument(self, instrument):
        """Get the audio for a particular instrument

        Args:
            instrument (str): the instrument to get audio for

        Returns:
            np.ndarray: instrument audio with shape (n_samples, n_channels)

        """
        assert instrument in self.instruments.keys()
        return getattr(
            self.tracks[self.instruments[instrument]], self.track_audio_property
        )[0]

    def get_audio_for_section(self, section):
        """Get the audio for a particular section

        Args:
            section (str): the section to get audio for

        Returns:
            np.ndarray: section audio with shape (n_samples, n_channels)

        """
        assert section in self.sections.keys()
        return self.get_target(self.sections[section])

    def get_notes_target(self, track_keys, notes_property="notes"):
        """Get the notes for all the tracks

        Args:
            * track_keys (list): list of track keys to get the NoteData for
            * notes_property (str): the attribute associated with NoteData, notes or notes_original

        Returns:
            NoteData: Note data for the tracks

        """
        values = []
        intervals = []
        for k in track_keys:
            score = getattr(self.tracks[k], notes_property)
            values.append(score.notes)
            intervals.append(score.intervals)
        values = np.hstack(values)
        intervals = np.vstack(intervals)

        #### sort on the start time
        ind = np.argsort(intervals[:, 0], axis=0)
        start_times = np.take_along_axis(intervals[:, 0], ind, axis=0)
        end_times = np.take_along_axis(intervals[:, 1], ind, axis=0)
        intervals = np.vstack([start_times, end_times]).T
        values = np.take_along_axis(values, ind, axis=0)

        return annotations.NoteData(intervals, values)

    def get_notes_for_instrument(self, instrument, notes_property="notes"):
        """Get the notes for a particular instrument

        Args:
            * instrument (str): the instrument to get the notes for
            * notes_property (str): the attribute associated with NoteData, notes or notes_original

        Returns:
            NoteData: Note data for the instrument

        """
        return getattr(self.tracks[self.instruments[instrument]], notes_property)

    def get_notes_for_section(self, section, notes_property="notes"):
        """Get the notes for a particular section

        Args:
            * section (str): the section to get the notes for
            * notes_property (str): the attribute associated with NoteData, notes or notes_original

        Returns:
            NoteData: Note data for the section

        """
        return self.get_notes_target(
            self.sections[section], notes_property=notes_property
        )


@io.coerce_to_bytes_io
def load_audio(fhandle: BinaryIO) -> Tuple[np.ndarray, float]:
    """Load a Phenicx-Anechoic audio file.

    Args:
        fhandle (str or file-like): File-like object or path to audio file

    Returns:
        * np.ndarray - the audio signal
        * float - The sample rate of the audio file

    """
    return librosa.load(fhandle, sr=None, mono=True)


@io.coerce_to_string_io
def load_score(fhandle: TextIO) -> annotations.NoteData:
    """Load a Phenicx-Anechoic score file.

    Args:
        fhandle (str or file-like): File-like object or path to score file

    Returns:
        NoteData: Note data for the given track
    """

    #### read start, end times
    intervals = np.loadtxt(fhandle, delimiter=",", usecols=[0, 1], dtype=np.float_)

    #### read notes as string
    fhandle.seek(0)
    content = fhandle.readlines()
    values = np.array(
        [
            librosa.note_to_hz(line.split(",")[2].strip("\n"))
            for line in content
        ]
    )

    return annotations.NoteData(intervals, values)


@core.docstring_inherit(core.Dataset)
class Dataset(core.Dataset):
    """
    The Phenicx-Anechoic dataset
    """

    def __init__(self, data_home=None):
        super().__init__(
            data_home,
            name="phenicx_anechoic",
            track_class=Track,
            multitrack_class=MultiTrack,
            bibtex=BIBTEX,
            remotes=REMOTES,
            license_info=LICENSE_INFO,
        )

    @core.copy_docs(load_audio)
    def load_audio(self, *args, **kwargs):
        return load_audio(*args, **kwargs)

    @core.copy_docs(load_score)
    def load_score(self, *args, **kwargs):
        return load_score(*args, **kwargs)
