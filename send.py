import sys
sys.path.append("../")
try:
	from bxbuild.tools import *
except:
	from tools import *

args = sys.argv
options = {}
lastarg = ''
for _ in args:
    if lastarg:
        if lastarg == 'u':
            lastarg = 'user'
        if lastarg == 'p':
            lastarg = 'password'
        options[lastarg] = _
        lastarg = ''
    else:
        if _[0] == '-':
            lastarg = _[1:]

send_update(options)