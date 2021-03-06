import gpflow
import numpy as np
import pickle
from multi_spectralmixture import MultiSpectralMixture as MOSM
from utils import zero_mean_unit_variance, normalize, entropy_from_cov
from arguments import get_args
# import matplotlib.pyplot as plt
# import pandas as pd
# import seaborn as sns
# sns.set(style="ticks", color_codes=True)


# assuming homotopic dataset (like Jura)
# X - num_datapoints X dim
# Y - num_datapoints X num_outputs
# load Jura dataset
def load_data(filename, features=None):
    with open(filename, 'rb') as fn:
        dct = pickle.load(fn)
    # dct has two keys: features and data
    # features: xloc, yloc, landuse, rock, Cd, Co, Cr, Cu, Ni, Pb, Zn
    if features is None:
        features = ['Cd', 'Ni', 'Zn']
    indices = np.array([dct['features'].index(f) for f in features])
    assert -1 not in indices, 'check your features!!'

    # X consists of only xloc and yloc
    X = dct['data'][:, :2]
    Y = dct['data'][:, indices]
    return X, Y


def mineral_exp_dataset(train_fn, test_fn, mineral, allies):    
    all_x_train, all_y_train, all_x_test, all_y_test = get_dataset(train_fn, test_fn, [mineral] + allies)

    # task/output index 0 corresponds to mineral
    are_minerals = all_x_test[:,0] == 0
    mineral_x_test = all_x_test[are_minerals]
    mineral_y_test = all_y_test[are_minerals]
    allies_x_test = all_x_test[~are_minerals]
    allies_y_test = all_y_test[~are_minerals]

    # add all test locations data of allies in the training set
    x1 = np.concatenate([all_x_train, allies_x_test], axis=0)
    y1 = np.concatenate([all_y_train, allies_y_test], axis=0)

    x2 = mineral_x_test
    y2 = mineral_y_test
    return x1, y1, x2, y2


def greedy(X, locs, sampled, K, num_samples, utility='entropy', heterotopic=True):
    # X - all sampling locations in the domain (n X (d + 1) )
    # 1st column of X represents the type of sample (thus compatible for heterotopic dataset)
    # sampled - boolean array representing whether sample has been collected or not (n x 1)
    n = len(X)
    new_samples = []
    cumm_utilies = []
    joint_entropy = entropy_from_cov(K)

    for i in range(num_samples):
        utilities = np.full(shape=n, fill_value=-np.inf)
        for j in range(n):
            if sampled[j]:
                continue
            sampled[j] = True
            cov = K[sampled].T[sampled].T
            entropy = entropy_from_cov(cov)

            if utility == 'entropy':
                ut = entropy
            elif utility == 'mutual_information':
                cov_rest = K[~sampled].T[~sampled].T
                entropy_rest = entropy_from_cov(cov_rest)
                ut = entropy + entropy_rest - joint_entropy
            else:
                raise NotImplementedError

            utilities[j] = ut
            sampled[j] = False

        best_sample = np.argmax(utilities)

        # if only one measurement is allowed at a location 
        if heterotopic:
            indices = (locs[:,0] == locs[best_sample,0]) * (locs[:,1] == locs[best_sample,1])
            sampled[indices] = True
        else:
            sampled[best_sample] = True

        new_samples.append(best_sample)
        cumm_utilies.append(utilities[best_sample])
    return np.array(new_samples)


# def render(X, locs, samples, num_outputs=3):
#     # plt.scatter(locs[:,0], locs[:,1])
#     # sampled_locs = locs[sampled]
#     # # the first column is the type of sample
#     # sample_type = X[sampled][:, 0]
#     # for i in range(num_outputs):
#     #     type_i_locs = sampled_locs[sample_type == i]
#     #     plt.scatter(type_i_locs[:,0], type_i_locs[:,1], label='type_'+str(i))
#     # plt.legend()
#     # plt.show()

#     x, y = locs.T
#     sx, sy = locs[samples].T
#     idx = X[samples][:, 0].astype(int)
#     all_x = np.concatenate([x, sx])
#     all_y = np.concatenate([y, sy])
#     all_idx = np.concatenate([np.full(len(x), num_outputs), idx])
#     df = pd.DataFrame(dict(x=all_x, y=all_y, idx=all_idx))
#     num_colors = len(np.unique(idx)) + 1
#     sns.relplot(data=df, x='x', y='y', hue='idx', palette=sns.color_palette('bright', num_colors))
#     plt.show()


def get_dataset(train_fn, test_fn, features=None):
    features = ['Cd', 'Ni', 'Zn'] if features is None else features
    X_train, Y_train = load_data(train_fn, features=features)
    X_test, Y_test = load_data(test_fn, features=features)
    
    train_locs = np.copy(X_train[:, :2])
    test_locs = np.copy(X_test[:, :2])

    # normalize datasets
    mean, std = X_train.mean(axis=0), X_train.std(axis=0)
    X_train = zero_mean_unit_variance(X_train, mean, std)
    X_test = zero_mean_unit_variance(X_test, mean, std)

    y_max = Y_train.max(axis=0)
    Y_train = normalize(Y_train, y_max)
    Y_test = normalize(Y_test, y_max)

    num_outputs = len(features)
    num_train = len(X_train)
    num_test = len(X_test)

    all_x_train = np.vstack([np.column_stack([np.full(shape=num_train, fill_value=i), X_train]) for i in range(num_outputs)])
    all_y_train = Y_train.T.flatten()[:, None]
    all_x_test = np.vstack([np.column_stack([np.full(shape=num_test, fill_value=i), X_test]) for i in range(num_outputs)])
    all_y_test = Y_test.T.flatten()[:, None]

    # sampling locations
    all_train_locs = np.concatenate([train_locs for _ in range(num_outputs)])
    all_test_locs = np.concatenate([test_locs for _ in range(num_outputs)])

    return all_x_train, all_y_train, all_x_test, all_y_test, all_train_locs, all_test_locs


if __name__ == '__main__':
    args = get_args()

    train_fn = 'datasets/jura_train_data.pkl'
    test_fn = 'datasets/jura_validation_data.pkl'
    
    # mineral = 'Cd'
    # allies = ['Ni', 'Zn']
    # X_train, Y_train, X_test, Y_test = mineral_exp_dataset(mineral, allies, train_fn, test_fn)

    features = ['Cd', 'Ni', 'Zn']
    X_train, Y_train, X_test, Y_test, train_locs, test_locs = get_dataset(train_fn, test_fn, features)
    input_size = X_train.shape[-1] - 1
    num_outputs = len(features)

    # uncomment the following lines to set initial values for the hyperparameters (not required)
    # weights_init = np.ones(num_outputs)
    # means_init = 0.5 * np.ones(num_outputs)[None, :]
    # var_init = np.ones(num_outputs)[None, :]
    # delay_init = np.zeros(num_outputs)[None, :]
    # phase_init = np.zeros(num_outputs)
    # kernel = MOSM(1, num_outputs, weights_init, means_init, var_init, delay_init, phase_init)

    # Set the number of components
    kernel = MOSM(input_size, num_outputs)
    for _ in range(args.n_components-1):
        kernel += MOSM(input_size, num_outputs)
    
    # initialize model
    model = gpflow.models.GPR(X_train, Y_train, kernel)
    model.likelihood.variance = 0.5

    # train model
    print('Learning model hyperparameters ... ')
    gpflow.train.ScipyOptimizer().minimize(model, disp=False, maxiter=args.max_iterations)
    y_pred, cov = model.predict_f_full_cov(X_test)
    cov = cov.squeeze()
    print('Done\n')

    print('Greedy Active Learning (adaptive sampling) ... ')
    sampled = np.full(shape=len(X_test), fill_value=False)
    new_samples = greedy(X_test, test_locs, sampled, cov,
                         num_samples=args.num_samples,
                         utility=args.utility,
                         heterotopic=args.heterotopic)

    sample_type = new_samples[:, 0] 
    sample_locs = test_locs[new_samples]

    # TODO: Once determining the sampling location and type of sample,
    # agent(s) can plan least cost path(s) to gather corresponding data 

    # predict at inputs given by X_pred
    # Y_pred, STD_pred = model.predict_y(X_test)  
    # rmse = np.linalg.norm(Y_pred - Y_test) / np.sqrt(len(Y_pred))