# Changelog

## [1.2.2](https://github.com/openfoodfacts/nutripatrol/compare/v1.2.1...v1.2.2) (2025-12-26)


### Bug Fixes

* add response models ([#118](https://github.com/openfoodfacts/nutripatrol/issues/118)) ([5784fec](https://github.com/openfoodfacts/nutripatrol/commit/5784fecb85fc6c92d09d8e9f6a5b9308f80c259f))
* Update README.md ([1506108](https://github.com/openfoodfacts/nutripatrol/commit/15061080f4cbc132b251b97918c8cd0da153d951))

## [1.2.1](https://github.com/openfoodfacts/nutripatrol/compare/v1.2.0...v1.2.1) (2025-07-22)


### Bug Fixes

* add new commands to Makefile ([#106](https://github.com/openfoodfacts/nutripatrol/issues/106)) ([4af6d08](https://github.com/openfoodfacts/nutripatrol/commit/4af6d0829d2f2f6ac9d47fa44edb872c9db5305b))

## [1.2.0](https://github.com/openfoodfacts/nutripatrol/compare/v1.1.2...v1.2.0) (2025-07-22)


### Features

* add a route to get some data on moderation ([#89](https://github.com/openfoodfacts/nutripatrol/issues/89)) ([6e0563a](https://github.com/openfoodfacts/nutripatrol/commit/6e0563ae338b2cb24933788e4266216c7182c2cc))
* cache user data ([0d85af9](https://github.com/openfoodfacts/nutripatrol/commit/0d85af9b57be40c33139e727c3e73b9d628754c9))
* prevent brut force and expired cache ([a256497](https://github.com/openfoodfacts/nutripatrol/commit/a256497db12ca04716957db612a08e474d0ddac1))
* protect routes ([a92e909](https://github.com/openfoodfacts/nutripatrol/commit/a92e9099a2686b7918503c586a12101576a7264e))
* route to paste cookie ([1324a17](https://github.com/openfoodfacts/nutripatrol/commit/1324a177a670f49a4c3c346acaa64d1028b67653))
* setup an auth middleware ([1e21f10](https://github.com/openfoodfacts/nutripatrol/commit/1e21f1034be85e70d0425f6bc0cc4d0f74f5fec2))


### Bug Fixes

* 1hour for expiration of cache ([c6c69e1](https://github.com/openfoodfacts/nutripatrol/commit/c6c69e10959ad8fb16a9726f78bc3bff990ec389))
* add route env to the docker compose ([fb99d08](https://github.com/openfoodfacts/nutripatrol/commit/fb99d08578016bd170b0ff847bef5a7660f3c2c2))
* Auth Middleware and protecting API routes ([#94](https://github.com/openfoodfacts/nutripatrol/issues/94)) ([c46db66](https://github.com/openfoodfacts/nutripatrol/commit/c46db667c67319874ff29e185210a1d217a7d7f8))
* build auth url using current domain ([737dd14](https://github.com/openfoodfacts/nutripatrol/commit/737dd14879fcfd673a3856fe8af55db3c1291879))
* check if user is moderator ([52d95a5](https://github.com/openfoodfacts/nutripatrol/commit/52d95a5bb8af9bd0902f1654ba06d444f765590c))
* comment local env variable ([2715d50](https://github.com/openfoodfacts/nutripatrol/commit/2715d5043a05f940360f1f6d557edcac26f43394))
* Deploy fix urlunparse missing args ([#104](https://github.com/openfoodfacts/nutripatrol/issues/104)) ([2d54654](https://github.com/openfoodfacts/nutripatrol/commit/2d5465439281f4975baf2f327cbcf19575854240))
* flake syntax ([5352894](https://github.com/openfoodfacts/nutripatrol/commit/5352894957630aec61b83a9ed74cd1a8a5659adf))
* format flake8 ([84e1ddc](https://github.com/openfoodfacts/nutripatrol/commit/84e1ddc55f3d25add28e6b9209dd057473f4d489))
* get user data func ([4cdb4dc](https://github.com/openfoodfacts/nutripatrol/commit/4cdb4dc67344659fd52c932e708e693f25fb8610))
* isort ([fcebf74](https://github.com/openfoodfacts/nutripatrol/commit/fcebf74961e7edf0e434bba74d9ff46126f04fe7))
* make middleware check user status ([b9172b1](https://github.com/openfoodfacts/nutripatrol/commit/b9172b119b22d3578d1f06e6425c18de4477d87d))
* pre-commit ([cc1fec1](https://github.com/openfoodfacts/nutripatrol/commit/cc1fec1db30c55470aec7cc83197bcaf8d49e8a5))
* READ ME explanation ([6b7aad2](https://github.com/openfoodfacts/nutripatrol/commit/6b7aad257a23b5b8f0b5c845bd253c6b79472f57))
* remove /auth route ([410c866](https://github.com/openfoodfacts/nutripatrol/commit/410c8664cae9bc0e293410196726bfbf99a7e4af))
* remove auth static const ([5f1acac](https://github.com/openfoodfacts/nutripatrol/commit/5f1acacf2a237905659784b05d3b2a892ad93295))
* remove PO_AUTH_ROUTE from .env ([4a506e8](https://github.com/openfoodfacts/nutripatrol/commit/4a506e8489a2582cd728b50a16d7d1c0349e9f6c))
* remove print ([e7cfe6d](https://github.com/openfoodfacts/nutripatrol/commit/e7cfe6d0327b67dbc2eade18e952b5dc4b40de63))
* remove unused create ticket route ([#96](https://github.com/openfoodfacts/nutripatrol/issues/96)) ([6a1760b](https://github.com/openfoodfacts/nutripatrol/commit/6a1760bf3b7248317fe13bd0e30f5e2f9d23fce9))
* Robotoff auth by bearer token ([#97](https://github.com/openfoodfacts/nutripatrol/issues/97)) ([195c6dc](https://github.com/openfoodfacts/nutripatrol/commit/195c6dcb572bf9678265b43368d60315e41bdff6))
* syntax fixes ([d4afd18](https://github.com/openfoodfacts/nutripatrol/commit/d4afd1861dff2125700ed635f95e2efdc60e2ff5))
* upgrade the Makerfile for docker compose ([28f9070](https://github.com/openfoodfacts/nutripatrol/commit/28f907009eaf9fec6739c6c72e3feeea276ad510))
* use decorator for cache ([c7ea737](https://github.com/openfoodfacts/nutripatrol/commit/c7ea7378bff215d030e3b4da76e4939fd1e82984))

## [1.1.2](https://github.com/openfoodfacts/nutripatrol/compare/v1.1.1...v1.1.2) (2024-05-15)


### Bug Fixes

* Filter tickets ([#53](https://github.com/openfoodfacts/nutripatrol/issues/53)) ([381edd8](https://github.com/openfoodfacts/nutripatrol/commit/381edd8c307bfad3be7b1825a464ee2924000525))

## [1.1.1](https://github.com/openfoodfacts/nutripatrol/compare/v1.1.0...v1.1.1) (2024-05-15)


### Bug Fixes

* add pagination ([#49](https://github.com/openfoodfacts/nutripatrol/issues/49)) ([96c42b1](https://github.com/openfoodfacts/nutripatrol/commit/96c42b1f71e79c032d30ca02db85f2aa0693f24e))
* return empty list when error ([#52](https://github.com/openfoodfacts/nutripatrol/issues/52)) ([fc472cb](https://github.com/openfoodfacts/nutripatrol/commit/fc472cbe80a319afaf0fd7ca785ecb65ad870e7a))

## [1.1.0](https://github.com/openfoodfacts/nutripatrol/compare/v1.0.2...v1.1.0) (2024-04-19)


### Features

* add route to get image Tickets ([#45](https://github.com/openfoodfacts/nutripatrol/issues/45)) ([3ec2a4f](https://github.com/openfoodfacts/nutripatrol/commit/3ec2a4f138e6a4816f57586195eb0e087606d4bd))
* docker nginx conf v1 ([#31](https://github.com/openfoodfacts/nutripatrol/issues/31)) ([e32baed](https://github.com/openfoodfacts/nutripatrol/commit/e32baed9c19a5f9fd72f27ab41948aeee15c1b73))


### Bug Fixes

* add cors middleware to Nutripatrol API ([#39](https://github.com/openfoodfacts/nutripatrol/issues/39)) ([67de9c6](https://github.com/openfoodfacts/nutripatrol/commit/67de9c6c033044fa1f3abf9fb0ce92e5f6b37f27))
* expose frontend on / instead of /app/ ([45937db](https://github.com/openfoodfacts/nutripatrol/commit/45937db8f839392aef78b6bd88a9617e56547912))
* restart policy nginx ([#43](https://github.com/openfoodfacts/nutripatrol/issues/43)) ([835e411](https://github.com/openfoodfacts/nutripatrol/commit/835e4111aec7ea4d4d3f4b63c275480561478895))
* wrong comment ([1ee8d43](https://github.com/openfoodfacts/nutripatrol/commit/1ee8d432f622344e7243646d0f3758a30c5ef606))

## [1.0.2](https://github.com/openfoodfacts/nutripatrol/compare/v1.0.1...v1.0.2) (2024-02-22)


### Bug Fixes

* add /api/v1 prefix to all API routes ([#34](https://github.com/openfoodfacts/nutripatrol/issues/34)) ([fff9add](https://github.com/openfoodfacts/nutripatrol/commit/fff9add510836d8833e6a11b5d063d2c892ebd83))

## [1.0.1](https://github.com/openfoodfacts/nutripatrol/compare/v1.0.0...v1.0.1) (2024-02-22)


### Technical

* fix production deployment settings ([a0e2827](https://github.com/openfoodfacts/nutripatrol/commit/a0e2827b3b9c99f00e6b4db3926c1e65fb355edb))

## 1.0.0 (2024-02-16)


### Features

* add basic project structure ([8ee769d](https://github.com/openfoodfacts/nutripatrol/commit/8ee769d3a877f959a2a4f63e2fb4ba744319f892))
* Add new routes and features for ticket and flag management (CRUD api) ([#15](https://github.com/openfoodfacts/nutripatrol/issues/15)) ([a9c6bf1](https://github.com/openfoodfacts/nutripatrol/commit/a9c6bf156298b4e1985524e1a4b018f6164ca3c1))
* make nutripatrol production-ready ([#29](https://github.com/openfoodfacts/nutripatrol/issues/29)) ([464a387](https://github.com/openfoodfacts/nutripatrol/commit/464a387e71ec37af7c0446fc4134e70102f1dd51))


### Bug Fixes

* fix container-deploy.yml config ([89d465d](https://github.com/openfoodfacts/nutripatrol/commit/89d465d12d5a0dd0b687a1fb3b1504b2c2eb9446))
* fix flake8 error ([3dfe6ae](https://github.com/openfoodfacts/nutripatrol/commit/3dfe6aea84e4df69f658fac61458cd9d4705ec81))
