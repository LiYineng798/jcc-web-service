"""Build the creator's static display font from the bundled OFL variable font.

Offline asset build only: requires fonttools[woff]. The derived family is
renamed to respect the original font's reserved name. No network is used.
"""
from pathlib import Path
import shutil

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'static/tools/lineup-simulator/fonts'
DESTINATION = ROOT / 'static/tools/orange-fortune/creator/fonts'


def main():
    print('Loading bundled font; preserving the full character set.', flush=True)
    font = TTFont(SOURCE / 'source-han-serif-sc-vf-subset.woff2', recalcTimestamp=False)
    print('Instantiating weight 600 (may take several minutes).', flush=True)
    # Keep CFF2's overlap handling: downgrading these outlines to CFF1 can
    # punch holes through intersecting Chinese strokes in browser renderers.
    instantiateVariableFont(font, {'wght': 600}, inplace=True)
    names = {
        1: 'JCC Editorial Serif', 2: 'SemiBold',
        3: 'JCCEditorialSerif-SemiBold-1.0', 4: 'JCC Editorial Serif SemiBold',
        6: 'JCCEditorialSerif-SemiBold', 16: 'JCC Editorial Serif', 17: 'SemiBold',
    }
    for record in font['name'].names:
        if record.nameID in names:
            record.string = names[record.nameID].encode(record.getEncoding())
    font.flavor = 'woff2'
    DESTINATION.mkdir(parents=True, exist_ok=True)
    print('Writing compressed font and OFL license.', flush=True)
    font.save(DESTINATION / 'jcc-editorial-serif-semibold.woff2')
    shutil.copyfile(SOURCE / 'LICENSE.txt', DESTINATION / 'LICENSE.txt')
    print('Creator display font ready.', flush=True)


if __name__ == '__main__':
    main()
