# C·D·F 분석 결과 (자동 생성)

- 설계 동결: c9836c5daa638d37c338234de8fdc7d79851b04906f5cb85761d239ec13687e3
- 생성: 2026-11-12 17:06:05

## C1. 운영점 EDR 0.80 / 0.90 / 0.95 (validation 재선택 → test)

|   target | set         | group   |   EDR |   FA_per_h |   lat_med |    n_FA | val_met_target(all seeds)   |
|---------:|:------------|:--------|------:|-----------:|----------:|--------:|:----------------------------|
|    0.800 | oops_test   | A       | 0.456 |    310.368 |     0.546 | 412.000 | True                        |
|    0.800 | oops_test   | B_W1    | 0.439 |    254.622 |     1.011 | 338.000 | True                        |
|    0.800 | oops_test   | B_W16   | 0.095 |    337.487 |     1.083 | 448.000 | False                       |
|    0.800 | oops_test   | B_W2    | 0.398 |    250.855 |     1.365 | 333.000 | True                        |
|    0.800 | oops_test   | B_W4    | 0.304 |    251.609 |     1.923 | 334.000 | True                        |
|    0.800 | oops_test   | B_W8    | 0.182 |    253.115 |     2.093 | 336.000 | False                       |
|    0.800 | oops_test   | C_W1    | 0.475 |    217.709 |     0.658 | 289.000 | True                        |
|    0.800 | oops_test   | C_W16   | 0.351 |    113.500 |     0.659 | 150.667 | True                        |
|    0.800 | oops_test   | C_W2    | 0.486 |    181.550 |     0.808 | 241.000 | True                        |
|    0.800 | oops_test   | C_W4    | 0.386 |    101.196 |     0.697 | 134.333 | True                        |
|    0.800 | oops_test   | C_W8    | 0.218 |     56.750 |     0.717 |  75.333 | True                        |
|    0.800 | staged_test | A       | 0.766 |     53.249 |     0.984 |  16.000 | True                        |
|    0.800 | staged_test | B_W1    | 0.719 |     39.937 |     1.529 |  12.000 | True                        |
|    0.800 | staged_test | B_W16   | 0.281 |    146.435 |     2.520 |  44.000 | False                       |
|    0.800 | staged_test | B_W2    | 0.750 |     36.609 |     2.160 |  11.000 | True                        |
|    0.800 | staged_test | B_W4    | 0.688 |     56.577 |     2.905 |  17.000 | True                        |
|    0.800 | staged_test | B_W8    | 0.391 |     69.890 |     3.384 |  21.000 | False                       |
|    0.800 | staged_test | C_W1    | 0.734 |     21.078 |     0.964 |   6.333 | True                        |
|    0.800 | staged_test | C_W16   | 0.703 |      6.656 |     0.971 |   2.000 | True                        |
|    0.800 | staged_test | C_W2    | 0.781 |     16.640 |     0.940 |   5.000 | True                        |
|    0.800 | staged_test | C_W4    | 0.734 |      9.984 |     0.984 |   3.000 | True                        |
|    0.800 | staged_test | C_W8    | 0.755 |      7.766 |     0.969 |   2.333 | True                        |
|    0.900 | oops_test   | A       | 0.399 |    340.500 |     0.446 | 452.000 | False                       |
|    0.900 | oops_test   | B_W1    | 0.404 |    284.755 |     0.949 | 378.000 | True                        |
|    0.900 | oops_test   | B_W16   | 0.095 |    337.487 |     1.083 | 448.000 | False                       |
|    0.900 | oops_test   | B_W2    | 0.365 |    265.168 |     1.325 | 352.000 | True                        |
|    0.900 | oops_test   | B_W4    | 0.290 |    261.402 |     1.811 | 347.000 | False                       |
|    0.900 | oops_test   | B_W8    | 0.182 |    253.115 |     2.093 | 336.000 | False                       |
|    0.900 | oops_test   | C_W1    | 0.452 |    258.389 |     0.633 | 343.000 | True                        |
|    0.900 | oops_test   | C_W16   | 0.379 |    128.566 |     0.655 | 170.667 | True                        |
|    0.900 | oops_test   | C_W2    | 0.483 |    209.925 |     0.748 | 278.667 | True                        |
|    0.900 | oops_test   | C_W4    | 0.417 |    133.840 |     0.686 | 177.667 | True                        |
|    0.900 | oops_test   | C_W8    | 0.254 |     81.610 |     0.722 | 108.333 | False                       |
|    0.900 | staged_test | A       | 0.859 |    119.811 |     0.792 |  36.000 | False                       |
|    0.900 | staged_test | B_W1    | 0.828 |     86.530 |     1.271 |  26.000 | True                        |
|    0.900 | staged_test | B_W16   | 0.281 |    146.435 |     2.520 |  44.000 | False                       |
|    0.900 | staged_test | B_W2    | 0.812 |     79.874 |     1.885 |  24.000 | True                        |
|    0.900 | staged_test | B_W4    | 0.656 |     73.218 |     2.705 |  22.000 | False                       |
|    0.900 | staged_test | B_W8    | 0.391 |     69.890 |     3.384 |  21.000 | False                       |
|    0.900 | staged_test | C_W1    | 0.849 |     35.499 |     0.905 |  10.667 | True                        |
|    0.900 | staged_test | C_W16   | 0.719 |     11.094 |     0.914 |   3.333 | True                        |
|    0.900 | staged_test | C_W2    | 0.839 |     28.843 |     0.920 |   8.667 | True                        |
|    0.900 | staged_test | C_W4    | 0.797 |     19.968 |     0.960 |   6.000 | True                        |
|    0.900 | staged_test | C_W8    | 0.781 |     15.531 |     0.862 |   4.667 | False                       |
|    0.950 | oops_test   | A       | 0.399 |    340.500 |     0.446 | 452.000 | False                       |
|    0.950 | oops_test   | B_W1    | 0.390 |    292.288 |     0.939 | 388.000 | False                       |
|    0.950 | oops_test   | B_W16   | 0.095 |    337.487 |     1.083 | 448.000 | False                       |
|    0.950 | oops_test   | B_W2    | 0.353 |    272.702 |     1.235 | 362.000 | False                       |
|    0.950 | oops_test   | B_W4    | 0.290 |    261.402 |     1.811 | 347.000 | False                       |
|    0.950 | oops_test   | B_W8    | 0.182 |    253.115 |     2.093 | 336.000 | False                       |
|    0.950 | oops_test   | C_W1    | 0.441 |    271.948 |     0.629 | 361.000 | True                        |
|    0.950 | oops_test   | C_W16   | 0.422 |    166.484 |     0.656 | 221.000 | False                       |
|    0.950 | oops_test   | C_W2    | 0.481 |    248.595 |     0.740 | 330.000 | False                       |
|    0.950 | oops_test   | C_W4    | 0.433 |    151.417 |     0.687 | 201.000 | True                        |
|    0.950 | oops_test   | C_W8    | 0.286 |    100.945 |     0.709 | 134.000 | False                       |
|    0.950 | staged_test | A       | 0.859 |    119.811 |     0.792 |  36.000 | False                       |
|    0.950 | staged_test | B_W1    | 0.875 |     93.186 |     1.259 |  28.000 | False                       |
|    0.950 | staged_test | B_W16   | 0.281 |    146.435 |     2.520 |  44.000 | False                       |
|    0.950 | staged_test | B_W2    | 0.797 |     73.218 |     1.760 |  22.000 | False                       |
|    0.950 | staged_test | B_W4    | 0.656 |     73.218 |     2.705 |  22.000 | False                       |
|    0.950 | staged_test | B_W8    | 0.391 |     69.890 |     3.384 |  21.000 | False                       |
|    0.950 | staged_test | C_W1    | 0.870 |     44.374 |     0.861 |  13.333 | True                        |
|    0.950 | staged_test | C_W16   | 0.781 |     26.625 |     0.818 |   8.000 | False                       |
|    0.950 | staged_test | C_W2    | 0.854 |     66.561 |     0.772 |  20.000 | False                       |
|    0.950 | staged_test | C_W4    | 0.823 |     24.406 |     0.921 |   7.333 | True                        |
|    0.950 | staged_test | C_W8    | 0.792 |     33.281 |     0.707 |  10.000 | False                       |

## C2. Staged test 95% CI: 녹화 단위 vs 피험자 단위 군집 부트스트랩

| level     | group   |   n_clusters |   EDR_lo |   EDR_hi |   FA_per_h_lo |   FA_per_h_hi |   lat_med_lo |   lat_med_hi |   pAUC_lo |   pAUC_hi |
|:----------|:--------|-------------:|---------:|---------:|--------------:|--------------:|-------------:|-------------:|----------:|----------:|
| recording | A       |           96 |    0.771 |    0.931 |        73.073 |       165.190 |        0.598 |        1.053 |     0.183 |     0.573 |
| recording | B_W1    |           96 |    0.746 |    0.915 |        46.135 |       131.034 |        1.130 |        1.453 |     0.108 |     0.561 |
| recording | B_W16   |           96 |    0.168 |    0.435 |       100.854 |       222.191 |        2.217 |        3.095 |     0.000 |     0.062 |
| recording | B_W2    |           96 |    0.714 |    0.897 |        42.449 |       121.616 |        1.740 |        2.253 |     0.125 |     0.506 |
| recording | B_W4    |           96 |    0.478 |    0.827 |        43.892 |       111.963 |        2.310 |        3.172 |     0.148 |     0.437 |
| recording | B_W8    |           96 |    0.255 |    0.545 |        41.840 |       101.044 |        2.708 |        4.471 |     0.000 |     0.051 |
| recording | C_W1    |           96 |    0.763 |    0.929 |        15.708 |        64.995 |        0.764 |        1.027 |     0.000 |     0.661 |
| recording | C_W16   |           96 |    0.620 |    0.825 |         3.581 |        21.378 |        0.731 |        1.126 |     0.554 |     0.815 |
| recording | C_W2    |           96 |    0.755 |    0.909 |        13.119 |        51.837 |        0.729 |        1.043 |     0.326 |     0.744 |
| recording | C_W4    |           96 |    0.716 |    0.881 |         9.999 |        33.881 |        0.735 |        1.096 |     0.560 |     0.797 |
| recording | C_W8    |           96 |    0.685 |    0.870 |         6.108 |        28.505 |        0.678 |        1.021 |     0.408 |     0.804 |
| subject   | A       |            7 |    0.727 |    0.967 |        58.390 |       247.331 |        0.576 |        1.164 |     0.073 |     0.711 |
| subject   | B_W1    |            7 |    0.742 |    0.926 |        29.403 |       205.390 |        1.130 |        1.680 |     0.010 |     0.649 |
| subject   | B_W16   |            7 |    0.135 |    0.482 |        74.992 |       247.413 |        2.229 |        2.679 |     0.000 |     0.073 |
| subject   | B_W2    |            7 |    0.690 |    0.938 |        29.254 |       185.976 |        1.730 |        2.372 |     0.067 |     0.560 |
| subject   | B_W4    |            7 |    0.446 |    0.880 |        24.141 |       185.940 |        2.290 |        3.249 |     0.070 |     0.492 |
| subject   | B_W8    |            7 |    0.233 |    0.596 |        34.609 |       150.772 |        2.960 |        5.172 |     0.000 |     0.015 |
| subject   | C_W1    |            7 |    0.719 |    0.985 |         9.115 |        89.039 |        0.719 |        1.190 |     0.087 |     0.854 |
| subject   | C_W16   |            7 |    0.521 |    0.917 |         3.612 |        16.779 |        0.697 |        1.300 |     0.543 |     0.866 |
| subject   | C_W2    |            7 |    0.649 |    0.995 |        13.313 |        52.986 |        0.674 |        1.126 |     0.237 |     0.893 |
| subject   | C_W4    |            7 |    0.622 |    0.968 |        10.566 |        35.708 |        0.655 |        1.197 |     0.438 |     0.901 |
| subject   | C_W8    |            7 |    0.565 |    0.968 |         4.687 |        23.945 |        0.631 |        1.123 |     0.443 |     0.911 |

## C3. 민감도 (조건군 평균)

| set         | variant              | group   |   n_events |   nonfall_h |   EDR |   FA_per_h |   lat_med |
|:------------|:---------------------|:--------|-----------:|------------:|------:|-----------:|----------:|
| oops_test   | base                 | A       |    631.000 |       1.327 | 0.399 |    340.500 |     0.446 |
| oops_test   | base                 | B_W1    |    631.000 |       1.327 | 0.404 |    284.755 |     0.949 |
| oops_test   | base                 | B_W16   |    631.000 |       1.327 | 0.095 |    337.487 |     1.083 |
| oops_test   | base                 | B_W2    |    631.000 |       1.327 | 0.365 |    265.168 |     1.325 |
| oops_test   | base                 | B_W4    |    631.000 |       1.327 | 0.290 |    261.402 |     1.811 |
| oops_test   | base                 | B_W8    |    631.000 |       1.327 | 0.182 |    253.115 |     2.093 |
| oops_test   | base                 | C_W1    |    631.000 |       1.327 | 0.452 |    258.389 |     0.633 |
| oops_test   | base                 | C_W16   |    631.000 |       1.327 | 0.379 |    128.566 |     0.655 |
| oops_test   | base                 | C_W2    |    631.000 |       1.327 | 0.483 |    209.925 |     0.748 |
| oops_test   | base                 | C_W4    |    631.000 |       1.327 | 0.417 |    133.840 |     0.686 |
| oops_test   | base                 | C_W8    |    631.000 |       1.327 | 0.254 |     81.610 |     0.722 |
| oops_test   | merge_gap=1.0s       | A       |    628.000 |       1.327 | 0.401 |    340.500 |     0.451 |
| oops_test   | merge_gap=1.0s       | B_W1    |    628.000 |       1.327 | 0.406 |    284.755 |     0.952 |
| oops_test   | merge_gap=1.0s       | B_W16   |    628.000 |       1.327 | 0.096 |    337.487 |     1.083 |
| oops_test   | merge_gap=1.0s       | B_W2    |    628.000 |       1.327 | 0.366 |    265.168 |     1.351 |
| oops_test   | merge_gap=1.0s       | B_W4    |    628.000 |       1.327 | 0.291 |    261.402 |     1.814 |
| oops_test   | merge_gap=1.0s       | B_W8    |    628.000 |       1.327 | 0.183 |    253.115 |     2.122 |
| oops_test   | merge_gap=1.0s       | C_W1    |    628.000 |       1.327 | 0.454 |    258.389 |     0.633 |
| oops_test   | merge_gap=1.0s       | C_W16   |    628.000 |       1.327 | 0.381 |    128.566 |     0.655 |
| oops_test   | merge_gap=1.0s       | C_W2    |    628.000 |       1.327 | 0.485 |    209.925 |     0.748 |
| oops_test   | merge_gap=1.0s       | C_W4    |    628.000 |       1.327 | 0.419 |    133.840 |     0.690 |
| oops_test   | merge_gap=1.0s       | C_W8    |    628.000 |       1.327 | 0.255 |     81.610 |     0.727 |
| oops_test   | positive=fall∪fallen | A       |    641.000 |       1.327 | 0.409 |    335.227 |     0.438 |
| oops_test   | positive=fall∪fallen | B_W1    |    641.000 |       1.327 | 0.417 |    279.481 |     0.940 |
| oops_test   | positive=fall∪fallen | B_W16   |    641.000 |       1.327 | 0.115 |    332.214 |     1.083 |
| oops_test   | positive=fall∪fallen | B_W2    |    641.000 |       1.327 | 0.378 |    260.648 |     1.298 |
| oops_test   | positive=fall∪fallen | B_W4    |    641.000 |       1.327 | 0.300 |    259.142 |     1.769 |
| oops_test   | positive=fall∪fallen | B_W8    |    641.000 |       1.327 | 0.193 |    250.102 |     1.957 |
| oops_test   | positive=fall∪fallen | C_W1    |    641.000 |       1.327 | 0.461 |    253.617 |     0.628 |
| oops_test   | positive=fall∪fallen | C_W16   |    641.000 |       1.327 | 0.384 |    123.293 |     0.658 |
| oops_test   | positive=fall∪fallen | C_W2    |    641.000 |       1.327 | 0.491 |    205.154 |     0.757 |
| oops_test   | positive=fall∪fallen | C_W4    |    641.000 |       1.327 | 0.422 |    129.320 |     0.694 |
| oops_test   | positive=fall∪fallen | C_W8    |    641.000 |       1.327 | 0.255 |     79.099 |     0.732 |
| staged_test | all_streams          | A       |     80.000 |       0.369 | 0.863 |    124.542 |     0.780 |
| staged_test | all_streams          | B_W1    |     80.000 |       0.369 | 0.800 |     81.223 |     1.276 |
| staged_test | all_streams          | B_W16   |     80.000 |       0.369 | 0.263 |    119.127 |     2.280 |
| staged_test | all_streams          | B_W2    |     80.000 |       0.369 | 0.725 |     70.393 |     1.960 |
| staged_test | all_streams          | B_W4    |     80.000 |       0.369 | 0.650 |     70.393 |     2.705 |
| staged_test | all_streams          | B_W8    |     80.000 |       0.369 | 0.388 |     67.686 |     3.384 |
| staged_test | all_streams          | C_W1    |     80.000 |       0.369 | 0.858 |     29.782 |     0.855 |
| staged_test | all_streams          | C_W16   |     80.000 |       0.369 | 0.750 |      9.927 |     0.877 |
| staged_test | all_streams          | C_W2    |     80.000 |       0.369 | 0.862 |     24.367 |     0.897 |
| staged_test | all_streams          | C_W4    |     80.000 |       0.369 | 0.804 |     17.147 |     0.892 |
| staged_test | all_streams          | C_W8    |     80.000 |       0.369 | 0.796 |     14.440 |     0.790 |
| staged_test | base                 | A       |     64.000 |       0.300 | 0.859 |    119.811 |     0.792 |
| staged_test | base                 | B_W1    |     64.000 |       0.300 | 0.828 |     86.530 |     1.271 |
| staged_test | base                 | B_W16   |     64.000 |       0.300 | 0.281 |    146.435 |     2.520 |
| staged_test | base                 | B_W2    |     64.000 |       0.300 | 0.812 |     79.874 |     1.885 |
| staged_test | base                 | B_W4    |     64.000 |       0.300 | 0.656 |     73.218 |     2.705 |
| staged_test | base                 | B_W8    |     64.000 |       0.300 | 0.391 |     69.890 |     3.384 |
| staged_test | base                 | C_W1    |     64.000 |       0.300 | 0.849 |     35.499 |     0.905 |
| staged_test | base                 | C_W16   |     64.000 |       0.300 | 0.719 |     11.094 |     0.914 |
| staged_test | base                 | C_W2    |     64.000 |       0.300 | 0.839 |     28.843 |     0.920 |
| staged_test | base                 | C_W4    |     64.000 |       0.300 | 0.797 |     19.968 |     0.960 |
| staged_test | base                 | C_W8    |     64.000 |       0.300 | 0.781 |     15.531 |     0.862 |
| staged_test | dataset=GMDCSA24     | A       |     17.000 |       0.060 | 0.765 |    117.275 |     1.040 |
| staged_test | dataset=GMDCSA24     | B_W1    |     17.000 |       0.060 | 0.706 |    117.275 |     1.630 |
| staged_test | dataset=GMDCSA24     | B_W16   |     17.000 |       0.060 | 0.235 |    201.043 |     2.600 |
| staged_test | dataset=GMDCSA24     | B_W2    |     17.000 |       0.060 | 0.588 |    100.521 |     2.380 |
| staged_test | dataset=GMDCSA24     | B_W4    |     17.000 |       0.060 | 0.471 |    100.521 |     3.090 |
| staged_test | dataset=GMDCSA24     | B_W8    |     17.000 |       0.060 | 0.235 |     67.014 |     3.550 |
| staged_test | dataset=GMDCSA24     | C_W1    |     17.000 |       0.060 | 0.647 |     55.845 |     1.260 |
| staged_test | dataset=GMDCSA24     | C_W16   |     17.000 |       0.060 | 0.412 |      5.585 |     1.280 |
| staged_test | dataset=GMDCSA24     | C_W2    |     17.000 |       0.060 | 0.490 |     50.261 |     1.220 |
| staged_test | dataset=GMDCSA24     | C_W4    |     17.000 |       0.060 | 0.490 |     39.092 |     1.193 |
| staged_test | dataset=GMDCSA24     | C_W8    |     17.000 |       0.060 | 0.392 |      5.585 |     1.213 |
| staged_test | dataset=caucafall    | A       |      9.000 |       0.035 | 0.667 |    318.710 |     1.190 |
| staged_test | dataset=caucafall    | B_W1    |      9.000 |       0.035 | 0.889 |    289.736 |     1.485 |
| staged_test | dataset=caucafall    | B_W16   |      9.000 |       0.035 | 0.333 |    405.631 |     2.500 |
| staged_test | dataset=caucafall    | B_W2    |      9.000 |       0.035 | 0.889 |    260.763 |     2.095 |
| staged_test | dataset=caucafall    | B_W4    |      9.000 |       0.035 | 0.778 |    289.736 |     3.060 |
| staged_test | dataset=caucafall    | B_W8    |      9.000 |       0.035 | 0.556 |    231.789 |     3.290 |
| staged_test | dataset=caucafall    | C_W1    |      9.000 |       0.035 | 0.889 |    135.210 |     1.035 |
| staged_test | dataset=caucafall    | C_W16   |      9.000 |       0.035 | 0.741 |      0.000 |     1.470 |
| staged_test | dataset=caucafall    | C_W2    |      9.000 |       0.035 | 1.000 |     86.921 |     1.160 |
| staged_test | dataset=caucafall    | C_W4    |      9.000 |       0.035 | 1.000 |     48.289 |     1.250 |
| staged_test | dataset=caucafall    | C_W8    |      9.000 |       0.035 | 1.000 |     28.974 |     1.120 |
| staged_test | dataset=edf          | A       |      8.000 |       0.038 | 0.875 |    105.798 |     1.249 |
| staged_test | dataset=edf          | B_W1    |      8.000 |       0.038 | 0.750 |     26.449 |     1.868 |
| staged_test | dataset=edf          | B_W16   |      8.000 |       0.038 | 0.125 |     26.449 |     3.653 |
| staged_test | dataset=edf          | B_W2    |      8.000 |       0.038 | 0.750 |     26.449 |     2.507 |
| staged_test | dataset=edf          | B_W4    |      8.000 |       0.038 | 1.000 |     26.449 |     3.777 |
| staged_test | dataset=edf          | B_W8    |      8.000 |       0.038 | 0.500 |    105.798 |     5.436 |
| staged_test | dataset=edf          | C_W1    |      8.000 |       0.038 | 0.667 |      0.000 |     1.341 |
| staged_test | dataset=edf          | C_W16   |      8.000 |       0.038 | 0.792 |      8.816 |     1.248 |
| staged_test | dataset=edf          | C_W2    |      8.000 |       0.038 | 0.833 |      8.816 |     1.184 |
| staged_test | dataset=edf          | C_W4    |      8.000 |       0.038 | 0.875 |      8.816 |     1.233 |
| staged_test | dataset=edf          | C_W8    |      8.000 |       0.038 | 0.750 |      0.000 |     1.103 |
| staged_test | dataset=le2i         | A       |     22.000 |       0.131 | 1.000 |     38.127 |     0.568 |
| staged_test | dataset=le2i         | B_W1    |     22.000 |       0.131 | 0.955 |     15.251 |     1.160 |
| staged_test | dataset=le2i         | B_W16   |     22.000 |       0.131 | 0.455 |    122.006 |     2.255 |
| staged_test | dataset=le2i         | B_W2    |     22.000 |       0.131 | 0.955 |     15.251 |     1.730 |
| staged_test | dataset=le2i         | B_W4    |     22.000 |       0.131 | 0.818 |     15.251 |     2.357 |
| staged_test | dataset=le2i         | B_W8    |     22.000 |       0.131 | 0.545 |     22.876 |     3.090 |
| staged_test | dataset=le2i         | C_W1    |     22.000 |       0.131 | 1.000 |     15.251 |     0.632 |
| staged_test | dataset=le2i         | C_W16   |     22.000 |       0.131 | 0.985 |     17.793 |     0.660 |
| staged_test | dataset=le2i         | C_W2    |     22.000 |       0.131 | 1.000 |     17.793 |     0.624 |
| staged_test | dataset=le2i         | C_W4    |     22.000 |       0.131 | 0.970 |     10.167 |     0.613 |
| staged_test | dataset=le2i         | C_W8    |     22.000 |       0.131 | 0.985 |     22.876 |     0.585 |
| staged_test | dataset=occu         | A       |      8.000 |       0.037 | 0.875 |    241.143 |     0.780 |
| staged_test | dataset=occu         | B_W1    |      8.000 |       0.037 | 0.750 |    160.762 |     0.860 |
| staged_test | dataset=occu         | B_W16   |      8.000 |       0.037 | 0.000 |     26.794 |   nan     |
| staged_test | dataset=occu         | B_W2    |      8.000 |       0.037 | 0.875 |    160.762 |     1.740 |
| staged_test | dataset=occu         | B_W4    |      8.000 |       0.037 | 0.125 |     80.381 |     0.000 |
| staged_test | dataset=occu         | B_W8    |      8.000 |       0.037 | 0.000 |     53.587 |   nan     |
| staged_test | dataset=occu         | C_W1    |      8.000 |       0.037 | 1.000 |     17.862 |     0.827 |
| staged_test | dataset=occu         | C_W16   |      8.000 |       0.037 | 0.542 |      8.931 |     0.900 |
| staged_test | dataset=occu         | C_W2    |      8.000 |       0.037 | 0.958 |      0.000 |     0.993 |
| staged_test | dataset=occu         | C_W4    |      8.000 |       0.037 | 0.667 |      8.931 |     0.860 |
| staged_test | dataset=occu         | C_W8    |      8.000 |       0.037 | 0.833 |      8.931 |     1.020 |
| staged_test | merge_gap=1.0s       | A       |     64.000 |       0.300 | 0.859 |    119.811 |     0.792 |
| staged_test | merge_gap=1.0s       | B_W1    |     64.000 |       0.300 | 0.828 |     86.530 |     1.271 |
| staged_test | merge_gap=1.0s       | B_W16   |     64.000 |       0.300 | 0.281 |    146.435 |     2.520 |
| staged_test | merge_gap=1.0s       | B_W2    |     64.000 |       0.300 | 0.812 |     79.874 |     1.885 |
| staged_test | merge_gap=1.0s       | B_W4    |     64.000 |       0.300 | 0.656 |     73.218 |     2.705 |
| staged_test | merge_gap=1.0s       | B_W8    |     64.000 |       0.300 | 0.391 |     69.890 |     3.384 |
| staged_test | merge_gap=1.0s       | C_W1    |     64.000 |       0.300 | 0.849 |     35.499 |     0.905 |
| staged_test | merge_gap=1.0s       | C_W16   |     64.000 |       0.300 | 0.719 |     11.094 |     0.914 |
| staged_test | merge_gap=1.0s       | C_W2    |     64.000 |       0.300 | 0.839 |     28.843 |     0.920 |
| staged_test | merge_gap=1.0s       | C_W4    |     64.000 |       0.300 | 0.797 |     19.968 |     0.960 |
| staged_test | merge_gap=1.0s       | C_W8    |     64.000 |       0.300 | 0.781 |     15.531 |     0.862 |
| staged_test | positive=fall∪fallen | A       |     64.000 |       0.300 | 0.875 |     99.842 |     0.796 |
| staged_test | positive=fall∪fallen | B_W1    |     64.000 |       0.300 | 0.844 |     76.546 |     1.276 |
| staged_test | positive=fall∪fallen | B_W16   |     64.000 |       0.300 | 0.297 |    146.435 |     2.540 |
| staged_test | positive=fall∪fallen | B_W2    |     64.000 |       0.300 | 0.828 |     66.561 |     1.890 |
| staged_test | positive=fall∪fallen | B_W4    |     64.000 |       0.300 | 0.656 |     73.218 |     2.705 |
| staged_test | positive=fall∪fallen | B_W8    |     64.000 |       0.300 | 0.500 |     59.905 |     4.109 |
| staged_test | positive=fall∪fallen | C_W1    |     64.000 |       0.300 | 0.849 |     35.499 |     0.905 |
| staged_test | positive=fall∪fallen | C_W16   |     64.000 |       0.300 | 0.719 |     11.094 |     0.914 |
| staged_test | positive=fall∪fallen | C_W2    |     64.000 |       0.300 | 0.839 |     28.843 |     0.920 |
| staged_test | positive=fall∪fallen | C_W4    |     64.000 |       0.300 | 0.797 |     19.968 |     0.960 |
| staged_test | positive=fall∪fallen | C_W8    |     64.000 |       0.300 | 0.781 |     15.531 |     0.862 |

## D3 (사후). 미검출 사건 분해: 사전 시작 묶음 vs 허용 구간 내 경보 없음 (조건군 평균)

| set         | group   |   n_missed |   pre_started |   pre_started_pct |   no_alarm_in_window |
|:------------|:--------|-----------:|--------------:|------------------:|---------------------:|
| oops_test   | A       |      379.0 |         330.0 |              87.1 |                 49.0 |
| oops_test   | B_W1    |      376.0 |         295.0 |              78.5 |                 81.0 |
| oops_test   | B_W16   |      571.0 |         504.0 |              88.3 |                 67.0 |
| oops_test   | B_W2    |      401.0 |         296.0 |              73.8 |                105.0 |
| oops_test   | B_W4    |      448.0 |         344.0 |              76.8 |                104.0 |
| oops_test   | B_W8    |      516.0 |         373.0 |              72.3 |                143.0 |
| oops_test   | C_W1    |      346.0 |         248.3 |              71.5 |                 97.7 |
| oops_test   | C_W16   |      392.0 |          64.3 |              16.4 |                327.7 |
| oops_test   | C_W2    |      326.3 |         173.3 |              53.1 |                153.0 |
| oops_test   | C_W4    |      368.0 |          78.3 |              21.1 |                289.7 |
| oops_test   | C_W8    |      471.0 |          43.3 |               9.2 |                427.7 |
| staged_test | A       |        9.0 |           3.0 |              33.3 |                  6.0 |
| staged_test | B_W1    |       11.0 |           3.0 |              27.3 |                  8.0 |
| staged_test | B_W16   |       46.0 |          35.0 |              76.1 |                 11.0 |
| staged_test | B_W2    |       12.0 |           2.0 |              16.7 |                 10.0 |
| staged_test | B_W4    |       22.0 |          11.0 |              50.0 |                 11.0 |
| staged_test | B_W8    |       39.0 |          12.0 |              30.8 |                 27.0 |
| staged_test | C_W1    |        9.7 |           0.0 |               0.0 |                  9.7 |
| staged_test | C_W16   |       18.0 |           0.0 |               0.0 |                 18.0 |
| staged_test | C_W2    |       10.3 |           0.0 |               0.0 |                 10.3 |
| staged_test | C_W4    |       13.0 |           0.0 |               0.0 |                 13.0 |
| staged_test | C_W8    |       14.0 |           0.0 |               0.0 |                 14.0 |

## D4 (사후). 사건 시작 전 W초 구간의 A 프레임 점수 평균 (사건 단위 → 집계)

| set         |   ('meanA_pre1s', 'mean') |   ('meanA_pre1s', 'median') |   ('meanA_pre2s', 'mean') |   ('meanA_pre2s', 'median') |   ('meanA_pre4s', 'mean') |   ('meanA_pre4s', 'median') |   ('meanA_pre8s', 'mean') |   ('meanA_pre8s', 'median') |   ('meanA_in_fall', 'mean') |   ('meanA_in_fall', 'median') |
|:------------|--------------------------:|----------------------------:|--------------------------:|----------------------------:|--------------------------:|----------------------------:|--------------------------:|----------------------------:|----------------------------:|------------------------------:|
| oops_test   |                     0.61  |                       0.659 |                     0.595 |                       0.629 |                     0.593 |                       0.636 |                     0.594 |                       0.632 |                       0.787 |                         0.871 |
| staged_test |                     0.309 |                       0.25  |                     0.304 |                       0.232 |                     0.311 |                       0.239 |                     0.324 |                       0.275 |                       0.666 |                         0.7   |

## F7. 그림 7 사례

- (a) Staged 검출 사례: le2i/Coffee_room_02/video_57 t0=17.2s (A·B(W=4)·C(W=4) 모두 검출, C 지연 0.8 s; 선정 규칙: 앞 맥락 ≥ 4 s 이고 세 조건 모두 검출한 사건 중 C(W=4) 지연이 중앙값에 가장 가까운 사건)
- (b) OOPS 미검출 사례: OOPS/falls/PolarVortexProblems10 t0=42.0s (C(W=4) 미검출, 사전 시작 묶음; 선정 규칙: 해당 유형 중 앞 맥락이 가장 긴 사건)

## G1. OOPS 미러 리비전

- pengxiang/oops @ 8ca3e64b264576404b1f80c94f11027a72f24f0e (last_modified 2025-04-04 13:11:06+00:00)
