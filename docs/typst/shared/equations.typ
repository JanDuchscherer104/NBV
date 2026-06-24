// Shared equation dictionary composed from domain-specific modules.

#import "equations/rri.typ": rri
#import "equations/coverage.typ": coverage
#import "equations/binning.typ": binning
#import "equations/coral.typ": coral
#import "equations/vin.typ": vin
#import "equations/metrics.typ": metrics
#import "equations/features.typ": features
#import "equations/scene.typ": scene
#import "equations/spatial.typ": spatial
#import "equations/model.typ": model
#import "equations/rl.typ": rl
#import "equations/action.typ": action
#import "equations/entity.typ": entity

#let eqs = (
  rri: rri,
  coverage: coverage,
  binning: binning,
  coral: coral,
  vin: vin,
  metrics: metrics,
  features: features,
  scene: scene,
  spatial: spatial,
  model: model,
  rl: rl,
  action: action,
  entity: entity,
)
