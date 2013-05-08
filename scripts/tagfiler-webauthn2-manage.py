#!/usr/bin/python

import web
web.config.debug = False
web.config.debug_sql = False

import sys
import tagfiler


def usage():
    print """
usage: tagfiler-webauthn2-manage <cmd>...

Run this utility to perform a sub-command to manipulate embedded
webauthn2 state of tagfiler service owned by the invoking daemon user.

  cmd: adduser <username>                (create user)
   or: deluser <username>                (remove user)

   or: passwd <username> <password>      (set user password)
   or: passwd <username> 'random'        (generate and set user password)
   or: passwd <username>                 (disable user password)

   or: addattr <attributename>           (create attribute)
   or: delattr <attributename>           (remove attribute)

   or: assign <username> <attribute>     (assign attribute to user)
   or: unassign <username> <attribute>   (unassign attribute from user)

   or: nest <child attr> <parent attr>   (make child attribute imply parent attribute)
   or: unnest <child attr> <parent attr> (make child attribute not imply parent attribute)

Exit status:

  0  for success
  1  for usage error
  2  for entity named in sub-command argument not found
  3  for sub-command not supported by current service configuration

"""

def main(args):
    try:
        if len(args) == 2 and args[0] == 'adduser':
            tagfiler.webauthn2_create_user(args[1])

        elif len(args) == 2 and args[0] == 'deluser':
            tagfiler.webauthn2_delete_user(args[1])

        elif len(args) == 2 and args[0] == 'addattr':
            tagfiler.webauthn2_create_attribute(args[1])

        elif len(args) == 2 and args[0] == 'delattr':
            tagfiler.webauthn2_delete_attribute(args[1])

        elif len(args) == 3 and args[0] == 'passwd':
            if args[2] == 'random':
                passwd = tagfiler.webauthn2_set_password(args[1], None)
                print 'new random password: %s' % passwd
            else:
                tagfiler.webauthn2_set_password(args[1], args[2])

        elif len(args) == 2 and args[0] == 'passwd':
            tagfiler.webauthn2_set_password(args[1], None)

        elif len(args) == 3 and args[0] == 'assign':
            tagfiler.webauthn2_assign_attribute(args[1], args[2])

        elif len(args) == 3 and args[0] == 'unassign':
            tagfiler.webauthn2_unassign_attribute(args[1], args[2])

        elif len(args) == 3 and args[0] == 'nest':
            tagfiler.webauthn2_nest_attribute(args[1], args[2])

        elif len(args) == 3 and args[0] == 'unnest':
            tagfiler.webauthn2_unnest_attribute(args[1], args[2])

        else:
            usage()
            return 1
        return 0

    except KeyError, ev:
        print 'not found: %s' % str(ev)
        return 2

    except NotImplementedError:
        print 'command not supported by current service configuration'
        return 3

if __name__ == '__main__':
    sys.exit( main(sys.argv[1:]) )

