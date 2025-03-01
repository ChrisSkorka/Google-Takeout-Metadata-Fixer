import os
import json

from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser

from typing import Generator


def fix_metadata(source_directory: Path, metadata_destination_directory: None | Path, metadata_suffix: str):

    for directory in get_depth_first_directories(source_directory):

        child_items_by_name: dict[str, Path] = {item.name: item for item in directory.iterdir()}
        primary_to_metadata_file_map: dict[Path, Path] = {}

        for name, path in child_items_by_name.items():
            if name.endswith(metadata_suffix):
                primary_item_name = name[:-len(metadata_suffix)]
                if primary_item_name in child_items_by_name:
                    primary_to_metadata_file_map[child_items_by_name[primary_item_name]] = path
        
        for primary_item, metadata_file in primary_to_metadata_file_map.items():
            apply_metadata(primary_item, metadata_file)
            if metadata_destination_directory:
                new_metadata_file = metadata_destination_directory / metadata_file.relative_to(source_directory)
                os.makedirs(new_metadata_file.parent, exist_ok=True)
                metadata_file.rename(new_metadata_file)


def get_depth_first_directories(path: Path) -> Generator[Path, None, None]:
    if path.is_dir():
        for entry in sorted(path.iterdir()):
            yield from get_depth_first_directories(entry)
        yield path


def apply_metadata(primary_item: Path, metadata_file: Path):
    metadata: dict = json.loads(metadata_file.read_text())
    last_modified: str = metadata['last_modified_by_any_user']
    modify_time = datetime.strptime(last_modified, "%Y-%m-%dT%H:%M:%S.%fZ")
    os.utime(primary_item, (modify_time.timestamp(), modify_time.timestamp()))


def rebase_pah(path: Path, old_base: Path, new_base: Path) -> Path:
    return new_base / path.relative_to(old_base)

def main():
    parser = ArgumentParser(
        prog='Google takeout Metadata Fixer',
       description=''
    )
    parser.add_argument(
        'source_directory',
       help='path to root directory of a Google Takeout',
    )
    parser.add_argument(
        'metadata_destination_directory',
        help='optional path to root directory where the metadata will be moved to',
       nargs='?',
    )
    parser.add_argument(
        '-s',
        '--suffix',
        default='-info.json',
        help='The suffix appended to the primary file name to identify the metadata file',
    )
    parsed_args = parser.parse_args()
    source_directory = Path(parsed_args.source_directory)
    metadata_destination_directory = Path(parsed_args.metadata_destination_directory) if parsed_args.metadata_destination_directory else None
    suffix = parsed_args.suffix
    fix_metadata(source_directory, metadata_destination_directory, suffix)

if __name__ == '__main__':
    main()
