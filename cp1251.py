import sys
sys.path.append("../")
try:
	from bxbuild.tools import *
except:
	from tools import *

conf = get_config()

module_path = os.path.abspath(conf["module_path"])
zip_name = os.path.abspath(conf["output_path"]+'.last_version.zip')

build_main(module_path, zip_name)
