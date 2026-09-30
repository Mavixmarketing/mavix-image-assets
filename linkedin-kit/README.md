# LinkedIn kit

Templates and renderer for the daily LinkedIn routine (Farhan + Nasir).
`kit.tgz` is what the routine downloads; `src/` is the same files, editable.
Rebuild the tarball after any edit:

    tar czf kit.tgz --exclude node_modules -s ',^src,kit,' src
