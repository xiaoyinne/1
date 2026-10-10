"""Run evo APE with its normal command line, including legacy mpl namespace fix."""
from pathlib import Path
import os
import matplotlib
import mpl_toolkits

mpl_toolkits.__path__ = [str(Path(matplotlib.__file__).parent.parent / 'mpl_toolkits')]

from evo.cli.entry_points import ape
from evo.tools.settings import SETTINGS

# evo may override MPLBACKEND with the user's saved Qt backend. Apply only
# a process-local setting so a headless venv does not require PyQt.
SETTINGS.plot_backend = os.environ.get('MPLBACKEND', 'Agg')

if __name__ == '__main__':
    ape()
