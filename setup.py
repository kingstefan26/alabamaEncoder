from setuptools import setup, find_packages

setup(
    name="alabamaEncoder",
    version="0.5.3",
    packages=find_packages(),
    install_requires=[
        "scenedetect",
        "tqdm",
        "celery",
        "redis",
        "psutil",
        "opencv-contrib-python",
        "requests",
        "torf",
        "websockets",
        "scipy",
        "numpy",
        "scikit-image",
        "argparse_range",
        "matplotlib",
    ],
    entry_points="""
      [console_scripts]
      alabamaEncoder=alabamaEncode.cli.__main__:main
      """,
)
