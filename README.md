# (Multi)mediasorter

> Inspired by https://github.com/joshuaboniface/mediasorter, rewritten from scratch with asyncio, enhanced pattern matching and packaged for easier installation/usage.

_"mediasorter is a tool to automatically "sort" media files from a source naming format
into something nicer for humans to read/organize, and for tools like Jellyfin to parse
and collect metadata for. It uses The Movie DB for movie metadata and TVMaze for
TV metadata to obtain additional information, then performs the "sort" via
a user-selectable mechanism. In this aspect it seeks to be a replacement for
FileBot and other similar tools."_

> See the [mediasorter-server](https://github.com/xyzjonas/mediasorter-server) project for a simple (yet useful) web app frontend.

## Installation

1. Install from PyPI.

    ``` bash
    pip install multimediasorter
    ```
2. Bootstrap a default configuration file, you will be prompted for your TMDB api key.
    ``` bash
    mediasorter --setup
    ```
3. Edit the configuration file with your TMDB API key (otherwise only TV shows searches will work).
4. See `--help` for more details.
   ```bash
   mediasorter --help
   ```


## Usage

### CLI args
You can specify a folder-to-be-sorted manually with the first positional argument.
By default, mediasorter tries to figure out the media type (`auto`), it then sorts TV show
and movies to their respective folders (if both arguments are used) or into a one single
common folder (if only single destination folder is specified).
```bash
mediasorter sort -m auto ./tests/test_data/ ~/Media/Series ~/Media/Movies
 ```


### Configuration
You can preconfigure folders to be sorted in your configuration YAML. See the `info` command
to find out what is configured and where to find your configuration file.
```bash
mediasorter info
```
Then simply append entries to the `scan_sources` section 
```yaml
# Use this to configure what directories should be sorted instead of the CLI argument(s).
scan_sources:

  - src_path: ~/Downloads-01
    media_type: auto  # force only a specific media type tv/movie/auto
    tv_shows_output: ~/Media/TV  # where to put recognized TV shows
    movies_output: ~/Media/Movies

  - src_path: ~/Downloads-02
    media_type: auto
    tv_shows_output: ~/Media/TV
    movies_output: ~/Media/Movies
```

### Search Overrides

Sometimes, the name of a piece of media, as extracted from the file, will not return
proper results from the upstream metadata providers. If this happens, `mediasorter`
includes an option in the configuration file to specify search overrides.
For example, the TV show "S.W.A.T." does not return sensible results, so it
can be overridden like so:

``` yaml
search_overrides:
   "s w a t": "swat"
   # ...
```

There's also a public .yaml with already discovered overrides in the root of this repository.
`mediasorter` uses it in conjunction with all the entries in the local configuration file.
PRs are welcomed!
