import urllib2, sys, subprocess, MySQLdb, json
from bs4 import BeautifulSoup
from time import time

reload(sys)
sys.setdefaultencoding('utf8')

with open('config.json', 'r') as f:
	config = json.load(f)

qualities = config['qualities']
resource = config['resource']
minimum_seeders = config['minseeders']
db = MySQLdb.connect(host=config['dbhost'], user=config['dbuser'], passwd=config['dbpass'], db=config['dbtable'])

def fetch():

	opener = urllib2.build_opener()
	opener.addheaders.append(('Cookie', config['cookie']))
	request = opener.open(resource)
	html = request.read()
	soup = BeautifulSoup(html, 'html.parser')
	data = soup.find('div', {'id': 'caltoday'})
	series = []
	for div in data.find_all('div', {'class': 'span12'}):
		serie = div.find('a', {'class': 'eplink'}).contents
		metadata = div.find('span', {'class': 'seasep'}).contents
		series.append({'title': serie[0].encode('utf-8'), 'episode': metadata[0][:-1]})

	
	cursor = db.cursor()

	for item in series:
		torrent = get_torrent(item)

		if torrent is not None:
			subprocess.call(['transmission-remote', '-a', torrent['magnet'], '-n', '%s:%s' % (config['truser'], config['trpass'])]) 
			if config['notify'] == 1:
				msg = 'Downloading item ' + torrent['title'] + ' ' + torrent['episode']
				long_msg_template = '<div><h4>Downloading item %s %s</h4><ul class="list-group">'
				long_msg_template += '<li class="list-group-item" style="padding-left: 10px;">'
				long_msg_template += '%s - %s<br />Seeders: %d ; Leechers %d;</li></ul></div>'
				long_msg = long_msg_template % (torrent['title'], torrent['episode'], torrent['torrent_title'], torrent['size'], torrent['seeders'], torrent['leechers'])
				query = "INSERT INTO `system_messages` VALUES (NULL, '%d', '%s', '0', '%d', '%d', '%s');"
				exec_query = query % (config['userid'], msg, config['severity'], int(time()), long_msg)
				cursor.execute(exec_query)
				db.commit()
		else:
			if config['notify'] == 1:
				msg = 'Failed to find torrent for item ' + item['title'] + ' ' + item['episode']
				query = "INSERT INTO `system_messages` VALUES (NULL, '%d', '%s', '0', '%d', '%d', NULL);"
				exec_query = query % (config['userid'], msg, config['severity'], int(time()))
				cursor.execute(exec_query)
				db.commit()

def get_torrent(item):
	query = urllib2.quote(item['title']) + '.' + item['episode']
	url = config['torquery'] % query
	torrent_request = urllib2.Request(url, headers={'User-Agent': 'Very Cool Browser'})
	torrent_response = urllib2.urlopen(torrent_request).read()

	soup = BeautifulSoup(torrent_response, 'html.parser')
	table = soup.find('table', {'id': 'searchResult'})
	items = []
	if table is not None:
		i = 0
		for tr in table.find_all('tr'):
			if i > 0:
				title = tr.find('a', {'class': 'detLink'})
				tmp = str(tr)
				magnet_start = tmp.index('magnet')
				magnet_end = tmp.index('"', magnet_start)
				magnet = urllib2.unquote(tmp[magnet_start:magnet_end]).replace('&amp;', '&')

				metadata = tr.find('font', {'class': 'detDesc'}).contents
				size_start = metadata[0].index('Size')
				size_end = metadata[0].index(',', size_start)
				size = metadata[0][size_start:size_end].replace(u'\xa0', ' ')

				it = {'title': item['title'], 'episode': item['episode'], 'torrent_title': title.contents[0].encode('utf-8'), 'magnet': magnet, 'size': size}
				j = 0
				for count in tr.find_all('td', {'align': 'right'}):
					if j == 0:
						it['seeders'] = int(count.contents[0])
					else:
						it['leechers'] = int(count.contents[0])
					j += 1
				items.append(it)
				
			i += 1

	return select_by_quality(items)

def select_by_quality(items):
	ret = None
	for quality in qualities:
		for item in items:
			try:
				name_len = len(item['title']) + len(item['episode']) + 2
				dot = item['torrent_title'].index('.', name_len+1)
				item_quality = item['torrent_title'][name_len:dot]
				if item_quality == quality and item['seeders'] > minimum_seeders:
					ret = item
					break
			except ValueError:
				pass
		if ret is not None:
			break
	return ret

if __name__ == "__main__":
	fetch()
