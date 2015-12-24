# coding=utf8
def run_vk():
    import vk_downloader
    vk_downloader.main()


def main():
	from pycallgraph import PyCallGraph
	from pycallgraph.output import GephiOutput	##GraphvizOutput
	graphviz = GephiOutput()			##GraphvizOutput()
	graphviz.output_file = 'pycallgraph.gdf'

	#C:\MY\GITHUB\vk_downloader\vk_downloader.py message ""  "WHO" 0 --MACHINE --DOWNLOAD_MP3=True
	#C:\MY\VK_DOWLOAD\Python27\App\python.exe C:\MY\GITHUB\vk_downloader\y_profiler.py message ""  "WHO" 0 --MACHINE==True --DOWNLOAD_MP3=True
	with PyCallGraph(output=graphviz):
		run_vk()

	# sort by time desc
	import sys
	fname = graphviz.output_file	#sys.argv[1]
	with open(fname,'r') as f:
		lines = f.read().split('\nedgedef>')[0].splitlines()[1:]
		arlines = map( lambda s: s.split(','), lines )
		#print map( lambda s: s[2], arlines )
		arlines = sorted( arlines, cmp = lambda x,y: cmp( float(y[4]), float(x[4]) ) )
	with open(fname+'.out','w') as f:
		f.write( '\n'.join( map(lambda s: '%.4f\t%s\t%s' %(float(s[4]),s[3],s[0]), arlines ) ) )


if __name__ == '__main__':
    main()
	