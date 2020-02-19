# rcs-to-git

Scripts to help convert RCS (the venerable but once-ubiquitous
Revision Control System, by Walter Tichy from Purdue) to git.

Since RCS worked at a file-level, different files checked
into RCS could have different revision numbers (unless
explicity specified), so reverse-engineering files into
commit groups requires some mining of metadata.

Also see the cvs-fast-import for an alternative.

Mark Moraes, 20200219
