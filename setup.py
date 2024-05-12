from setuptools import setup, find_packages

setup(
    name="alabamaEncoder",
    version="0.4",
    packages=find_packages(),
    install_requires=[
        "scenedetect",
        "tqdm",
        "celery",
        "redis",
        "psutil",
        "opencv-python",
        "requests",
        "torf",
        "websockets",
        "argparse_range",
    ],
    entry_points="""
      [console_scripts]
      alabamaEncoder=alabamaEncode_frontends.cli.__main__:main
      """,
)
