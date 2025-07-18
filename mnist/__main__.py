import sys, os, subprocess
import argparse

#python check
if sys.version_info[:2] != (3, 12):
    raise RuntimeError('This module is intended to be run on Python 3.12.')

#console input
parser = argparse.ArgumentParser()
parser.add_argument('dataset', metavar = 'normal data')
parser.add_argument('anomaly', metavar = 'anomalous data')
parser.add_argument('--log', metavar = 'logging level', default = 'INFO')
args = parser.parse_args()

#CUDA version scan
sh = 'nvidia-smi'
sh_ = subprocess.run('which ' + sh, shell = True, capture_output = True, text = True).stdout
if sh_ == '':
    cuda_version = None
else:
    sh_ = subprocess.run(
        sh,
        shell = True, capture_output = True, text = True,
        ).stdout
    cuda_version = sh_.split()
    cuda_version = cuda_version[cuda_version.index('CUDA') + 2]


from environment import *
logger = logging.getLogger(name = 'main')
logging.basicConfig(level = args.log)
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

from loader import Loader
from models import Autoencoder
from trainer import Trainer
from anomaly_detector import AnomalyDetector
from plotter import Plotter
from utils import Sampler, DimensionEstimator

#gpu driver check
if None in [torch.version.cuda, cuda_version]:
    if torch.version.cuda is None:
        logger.info('The installed pytorch is not built with CUDA. Install a CUDA-enabled.')
    if cuda_version is None:
        logger.info('The nvidia driver does not exist.')
elif float(cuda_version) < float(torch.version.cuda):
    logger.info('The supported CUDA is lower than installed. Upgrade the driver.')
else:
    logger.info('- Nvidia driver checked -')


dataset = args.dataset
anomaly = args.anomaly

#tools
sampler = Sampler()
estimator = DimensionEstimator()

#load
loader = Loader()
X = loader.load(dataset)
X_ = loader.load(dataset, train = False)

"""
logger.info('Intrinsic Dimension: {dimension}'.format(
    dimension = estimator(X, exact = True, trim = True),
    ))
"""


# - prepared -

#train
normal = X.copy()
anomalous = sampler.sample(
    loader.load(anomaly),
    len(normal) // 9,
    )
contaminated = np.concatenate([
    normal,
    anomalous,
    ], axis = 0)
truth = np.zeros([len(contaminated)], dtype = 'int64')
truth[len(normal):] = 1
truth = truth.astype('bool')

#test
normal_ = X_.copy()
anomalous_ = sampler.sample(
    loader.load(anomaly, train = False),
    len(normal_) // 9,
    )
contaminated_ = np.concatenate([
    normal_,
    anomalous_
    ], axis = 0)
truth_ = np.zeros([len(contaminated_)], dtype = 'int64')
truth_[len(normal_):] = 1
truth_ = truth_.astype('bool')


#model
ae = Autoencoder()

#trained
trainer = Trainer()
trainer.train(X, ae)
descent = trainer.plot_losses()


# - plots -

plotter = Plotter()
figures = {}

figures['descent'] = trainer.plot_losses()

figures['errors-train'] = plotter.errors(normal, anomalous, ae)
figures['dashes-train'] = plotter.dashes(normal, ae)
figures['boxes-train'] = plotter.boxes(normal, ae)
figures['violins-train'] = plotter.violins(normal, ae)

figures['errors-test'] = plotter.errors(normal_, anomalous_, ae)
figures['dashes-test'] = plotter.dashes(normal_, ae)
figures['boxes-test'] = plotter.boxes(normal_, ae)
figures['violins-test'] = plotter.violins(normal_, ae)

#saved
os.makedirs('figures', exist_ok = True)
for l in figures:
    figures[l].savefig('figures/{title}.png'.format(
        title = l
        ), dpi = 300)


# - anomaly detection -

#traditional
forest = IsolationForest()
forest.fit(normal)
forest_pred = forest.predict(contaminated) < 0
forest_pred_ = forest.predict(contaminated_) < 0
print('\n\n')
print('-- Isolation Forest --\n')
print('F1 (train): {f1}'.format(
    f1 = round(f1_score(truth, forest_pred), ndigits = 3),
    ))
print('F1  (test): {f1}'.format(
    f1 = round(f1_score(truth_, forest_pred_), ndigits = 3),
    ))
print('\n')

#deep learning
detector = AnomalyDetector(normal, anomalous, ae)
print('   --- Train ---')
prediction = detector.predict(contaminated, label = truth)
print('   --- Test ---')
prediction = detector.predict(contaminated_, label = truth_)
