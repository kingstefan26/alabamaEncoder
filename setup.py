from setuptools import setup, find_packages

setup(
    name='video_encoder',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'scenedetect', 'tqdm', 'celery', 'redis', 'psutil', 'opencv-python'
    ],
    entry_points='''
      [console_scripts]
      alabamaEncoder=hoeEncode.__main__:main
      ''',
)
