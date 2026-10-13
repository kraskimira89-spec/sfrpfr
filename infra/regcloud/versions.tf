terraform {
  required_version = ">= 1.5.0"

  required_providers {
    regcloud = {
      source  = "tf.reg.cloud/regru/regcloud"
      version = ">= 0.0.15"
    }
  }
}
