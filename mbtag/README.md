# mbtag
work in progress

tagging utility which is part of shira
primary use is to add MusicBrainz ID tags to existing songs which were not downlaoded by shira

```
Usage: python -m mbtag [OPTIONS] INPUT_PATH

Options:
  -c, --fetch-complete  Fetch from MusicBrainz even if has mb_releasetrackid, 
                        mb_releasegroupid, mb_artistid, mb_albumartistid      
                        present.
  -p, --fetch-partial   Fetch from MusicBrainz even if has some mb_* tags     
                        present.
  -d, --dry-run         Don't write to any files, just print out the mb_* tags
  -g, --debug           Prints out extra information for debugging. Does not  
                        imply --dry-run.
  --help                Show this message and exit.
```