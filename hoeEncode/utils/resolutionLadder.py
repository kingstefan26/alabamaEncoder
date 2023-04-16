def get_quality_preset(resolution_canon_name):
    if resolution_canon_name == '360p':
        return '-vf scale=-2:360'
    elif resolution_canon_name == '480p':
        return '-vf scale=-2:468'
    elif resolution_canon_name == '720p':
        return '-vf scale=-2:720'
    elif resolution_canon_name == '1080p':
        return '-vf scale=-2:1080'
    else:
        return ''
