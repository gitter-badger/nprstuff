#!/usr/bin/env python

import os, sys, glob, numpy, urllib2, mutagen.mp4
import multiprocessing, time, lxml.etree, subprocess
sys.path.append('/mnt/software/sources/nprstuff')
import npr_utils

def get_freshair_image():
    return urllib2.urlopen('http://media.npr.org/images/podcasts/2013/primary/fresh_air.png').read()

# get NPR API tag for this program
# nprApiDate=$(date --date="$1" +%Y-%m-%d) ;
# nprURL="http://api.npr.org/query?id=13&date="$nprApiDate"&dateType=story&output=NPRML&apiKey=MDA2OTgzNTcwMDEyOTc1NDg4NTNmMWI5Mg001" ;
def get_freshair_URL(datetime_s):
    nprApiDate = time.strftime('%Y-%m-%d', datetime_s)
    return 'http://api.npr.org/query?id=13&date=%s&dateType=story&output=NPRML&apiKey=MDA2OTgzNTcwMDEyOTc1NDg4NTNmMWI5Mg001' % nprApiDate

def _download_file(input_tuple):
    mp3URL, filename = input_tuple
    with open(filename, 'wb') as openfile:
        openfile.write( urllib2.urlopen(mp3URL).read() )

def get_freshair(outputdir, datetime_wkday, order_totnum = None,
                 file_data = None):
    
    # check if outputdir is a directory
    if not os.path.isdir(outputdir):
        raise ValueError("Error, %s is not a directory." % outputdir)

    # check if actually a weekday
    datetime_s = npr_utils.get_sanitized_time(datetime_wkday)
    if not npr_utils.is_weekday(datetime_s):
        raise ValueError("Error, date = %s not a weekday." %
                         npr_utils.get_datestring(datetime_s) )

    if order_totnum is None:
        order_totnum = npr_utils.get_order_number_weekday_in_year(datetime_s)
    order_in_year, tot_in_year = order_totnum

    if file_data is None:
        file_data = get_freshair_image()
    
    nprURL = get_freshair_URL(datetime_s)
    year = datetime_s.tm_year
    
    # download this data into an lxml elementtree
    tree = lxml.etree.fromstring( urllib2.urlopen(nprURL).read())
    
    # now get tuple of title to mp3 file
    title_mp3_urls = []
    for elem in tree.iter('story'):
        title = list( elem.iter('title') )[0].text.strip()
        m3uurl = max( elem.iter('mp3') ).text.strip()
        mp3url = urllib2.urlopen( m3uurl ).read().strip()
        title_mp3_urls.append( ( title, mp3url ) )
    
    decdate = time.strftime('%Y.%m.%d', datetime_s)
    
    titles, mp3urls = zip(*title_mp3_urls)
    title = time.strftime('%A, %B %d, %Y', datetime_s)
    title = '%s: %s.' % ( title,
                          '; '.join([ '%d) %s' % ( num + 1, titl ) for
                                      (num, titl) in enumerate(titles) ]) )    
    outfiles = [ os.path.join(outputdir, 'freshair.%s.%d.mp3' % 
                              ( decdate, num + 1) ) for
                 (num, mp3url) in enumerate( mp3urls) ]
    
    # download those files
    time0 = time.time()
    pool = multiprocessing.Pool(processes = len(mp3urls) )
    pool.map(_download_file, zip( mp3urls, outfiles ) )
    
    # sox magic command
    time0 = time.time()
    wgdate = time.strftime('%d-%b-%Y', datetime_s)
    wavfile = os.path.join(outputdir, 'freshair%s.wav' % wgdate ).replace(' ', '\ ')
    fnames = [ filename.replace(' ', '\ ') for filename in outfiles ]
    split_cmd = [ '(for', 'file', 'in', ] + fnames + [ 
        ';', '/usr/bin/sox', '$file', '-t', 'cdr', '-', ';', 'done)' ] + [ 
            '|', '/usr/bin/sox', 't-', 'cdr', '-', wavfile ]
    split_cmd = [ '/usr/bin/sox', ] + fnames + [ wavfile, ]
    proc = subprocess.Popen(split_cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout_val, stderr_val = proc.communicate()
    for filename in outfiles:
        os.remove(filename)

    # now convert to m4a file
    # /usr/bin/avconv -y -i freshair$wgdate.wav -ar 44100 -ac 2 -aq 400 -acodec libfaac NPR.FreshAir."$decdate".m4a ;
    m4afile = os.path.join(outputdir, 'NPR.FreshAir.%s.m4a' % decdate )
    split_cmd = [ '/usr/bin/avconv', '-y', '-i', wavfile, '-ar', '44100', '-ac', '2',
                  '-strict', 'experimental', '-acodec', 'aac', m4afile ]
    proc = subprocess.Popen(split_cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout_val, stderr_val = proc.communicate()
    
    # remove wav file
    os.remove( wavfile )
    
    # now put in metadata
    mp4tags = mutagen.mp4.MP4(m4afile)
    mp4tags.tags['\xa9nam'] = [ title, ]
    mp4tags.tags['\xa9alb'] = [ 'Fresh Air From WHYY: %d' % year, ]
    mp4tags.tags['\xa9ART'] = [ 'Terry Gross', ]
    mp4tags.tags['\xa9day'] = [ '%d' % year, ]
    mp4tags.tags['\xa9cmt'] = [ "more info at : Fresh Air from WHYY and NPR Web site", ]
    mp4tags.tags['trkn'] = [ ( order_in_year, tot_in_year ), ]
    mp4tags.tags['covr'] = [ mutagen.mp4.MP4(file_data, mutagen.mp4.MP4Cover.FORMAT_PNG ), ]
    mp4tags.save()
