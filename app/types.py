import dataclasses
import enum


class ServerType(str, enum.Enum):
    """ServerType is used to refer to a specific Open*Facts project:

    - Open Food Facts
    - Open Beauty Facts
    - Open Pet Food Facts
    - Open Product Facts
    - Open Food Facts (Pro plateform)
    """

    off = "off"
    obf = "obf"
    opff = "opff"
    opf = "opf"
    off_pro = "off-pro"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def get_base_domain(self) -> str:
        """Get the base domain (domain without TLD and without world/api
        subdomain) associated with the `ServerType`."""
        if self == self.off:
            return "openfoodfacts"
        elif self == self.obf:
            return "openbeautyfacts"
        elif self == self.opff:
            return "openpetfoodfacts"
        elif self == self.opf:
            return "openproductfacts"
        else:
            # Open Food Facts Pro
            return "pro.openfoodfacts"

    @classmethod
    def from_product_type(cls, product_type: str) -> "ServerType":
        """Get the `ServerType` associated with a product type."""
        if product_type == "food":
            return cls.off
        elif product_type == "beauty":
            return cls.obf
        elif product_type == "petfood":
            return cls.opff
        elif product_type == "product":
            return cls.opf
        raise ValueError(f"no ServerType matched for product_type {product_type}")

    @classmethod
    def get_from_server_domain(cls, server_domain: str) -> "ServerType":
        """Get the `ServerType` associated with a `server_domain`."""
        subdomain, base_domain, tld = server_domain.rsplit(".", maxsplit=2)

        if subdomain == "api.pro":
            if base_domain == "openfoodfacts":
                return cls.off_pro
            raise ValueError("pro platform is only available for Open Food Facts")

        for server_type in cls:
            if base_domain == server_type.get_base_domain():
                return server_type

        raise ValueError(f"no ServerType matched for server_domain {server_domain}")

    def is_food(self) -> bool:
        """Return True if the server type is `off` or `off-pro`, False
        otherwise."""
        return self in (self.off, self.off_pro)


@dataclasses.dataclass
class ProductIdentifier:
    """Dataclass to uniquely identify a product across all Open*Facts
    projects, with:

    - the product barcode: for the pro platform, it must be in the format
      `{ORG_ID}/{BARCODE}` (ex: `org-lea-nature/3307130803004`), otherwise it's
      the barcode only
    - the project specified by the ServerType
    """

    barcode: str
    server_type: ServerType

    def __repr__(self) -> str:
        return "<Product %s | %s>" % (self.barcode, self.server_type.name)

    def __hash__(self) -> int:
        return hash((self.barcode, self.server_type))

    def is_valid(self) -> bool:
        return bool(self.barcode and self.server_type)
