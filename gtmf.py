# pyright: strict

from abc import ABC, abstractmethod
import os
import json

from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser
import sys
from typing import Any, Generator, Self, Type
from html.parser import HTMLParser


class MetadataParser(ABC):
    def __init__(self, metadata_path: Path, primary_path: Path) -> None:
        self.metadata_path = metadata_path
        self.primary_path = primary_path

    @classmethod
    @abstractmethod
    def get_compatible_suffixes(cls) -> list[str]:
        pass

    @classmethod
    @abstractmethod
    def create(cls, metadata_path: Path) -> None | Self:
        pass

    @abstractmethod
    def apply_metadata_to_primary(self) -> bool:
        pass

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({repr(self.metadata_path)}, {repr(self.primary_path)})'


class JsonParser(MetadataParser):
    def __init__(self, metadata_path: Path, primary_path: Path, data: dict[str, Any]) -> None:
        super().__init__(metadata_path, primary_path)
        self.data = data

    @classmethod
    def get_compatible_suffixes(cls) -> list[str]:
        return ['.json']

    @classmethod
    def create(cls, metadata_path: Path) -> None | Self:
        try:
            data: None | dict[str, Any] = json.loads(metadata_path.read_text())
            if data == None:
                return None

            title = data.get('title', None)
            if title is None:
                return None

            primary_path = metadata_path.parent.joinpath(title)
            if primary_path.exists():
                return cls(metadata_path, primary_path, data)

            primary_path = primary_path.parent
            if primary_path.exists():
                return cls(metadata_path, primary_path, data)

            return None

        except Exception:
            return None

    def apply_metadata_to_primary(self) -> bool:
        try:
            if 'last_modified_by_any_user' in self.data:
                timestamp = datetime.strptime(
                    self.data['last_modified_by_any_user'],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                )
                return self.apply_modify_timestamp(timestamp.timestamp())

            if 'photoTakenTime' in self.data and 'timestamp' in self.data['photoTakenTime']:
                timestamp = float(self.data['photoTakenTime']['timestamp'])
                return self.apply_modify_timestamp(timestamp)

            if 'date' in self.data and 'timestamp' in self.data['date']:
                timestamp = float(self.data['date']['timestamp'])
                return self.apply_modify_timestamp(timestamp)

        except Exception:
            return False
        return False

    def apply_modify_timestamp(self, timestamp: float) -> bool:
        os.utime(self.primary_path, (timestamp, timestamp))
        return True


class CommentsHtmlParser(MetadataParser):

    class TitleParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.title: None | str = None
            self.path: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
            self.path.append(tag)

        def handle_endtag(self, tag: str):
            self.path.pop()

        def handle_data(self, data: str):
            if self.path == ['html', 'title']:
                self.title = data

    @classmethod
    def get_compatible_suffixes(cls) -> list[str]:
        return ['.html']

    @classmethod
    def create(cls, metadata_path: Path) -> None | Self:
        try:
            parser = CommentsHtmlParser.TitleParser()
            parser.feed(metadata_path.read_text())

            title = parser.title
            if title is None:
                return None

            primary_path = metadata_path.parent.joinpath(title)
            if not primary_path.exists():
                return None

            return cls(metadata_path, primary_path)

        except Exception:
            return None

    def apply_metadata_to_primary(self) -> bool:
        return True


metadata_parsers: list[Type[MetadataParser]] = [
    JsonParser,
    CommentsHtmlParser,
]


def fix_metadata(source_directory: Path, metadata_destination_directory: None | Path):

    for directory in get_depth_first_directories(source_directory):

        child_items_by_name: dict[str, Path] = {
            item.name: item
            for item
            in directory.iterdir()
        }

        parsers: list[MetadataParser] = [
            parser
            for (metadata_name, metadata_path) in child_items_by_name.items()
            for parser_cls in metadata_parsers
            for suffix in parser_cls.get_compatible_suffixes()
            if metadata_name.endswith(suffix)
            if (parser := parser_cls.create(metadata_path)) is not None
        ]

        for metadata_parser in parsers:
            try:
                is_applied = metadata_parser.apply_metadata_to_primary()
                if is_applied and metadata_destination_directory:
                    metadata_parser.metadata_path = move_metadata_file(
                        metadata_parser.metadata_path,
                        source_directory,
                        metadata_destination_directory,
                    )
                print(
                    f'Fixed metadata for {metadata_parser.primary_path} with {metadata_parser.metadata_path}')
            except Exception as e:
                print(metadata_parser.metadata_path, repr(e), file=sys.stderr)


def get_depth_first_directories(path: Path) -> Generator[Path, None, None]:
    if path.is_dir():
        for entry in sorted(path.iterdir()):
            yield from get_depth_first_directories(entry)
        yield path


def move_metadata_file(
    metadata_path: Path,
    source_directory: Path,
    metadata_destination_directory: Path,
) -> Path:
    new_metadata_path = Path.joinpath(
        metadata_destination_directory,
        metadata_path.relative_to(source_directory),
    )
    os.makedirs(new_metadata_path.parent, exist_ok=True)
    metadata_path.rename(new_metadata_path)
    return new_metadata_path


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
    parsed_args = parser.parse_args()
    
    # parse and check source_directory
    source_directory: Path = Path(parsed_args.source_directory)
    source_directory.mkdir(parents=True, exist_ok=True)
    assert source_directory.is_dir(), 'source_directory must be a directory'
    
    # parse and check metadata_destination_directory
    metadata_destination_directory: None | Path = None
    if parsed_args.metadata_destination_directory is not None:
        metadata_destination_directory = Path(parsed_args.metadata_destination_directory)
        metadata_destination_directory.mkdir(parents=True, exist_ok=True)
        assert metadata_destination_directory.is_dir(), 'metadata_destination_directory must be a directory'    

    # fix metadata
    fix_metadata(source_directory, metadata_destination_directory)


if __name__ == '__main__':
    main()
