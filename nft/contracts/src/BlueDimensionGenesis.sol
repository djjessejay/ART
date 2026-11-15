// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {ERC2981} from "@openzeppelin/contracts/token/common/ERC2981.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";

/// @title Blue Dimension Genesis
/// @notice 1/1-Kollektion mit fester Maximalmenge, IPFS-Metadaten und ERC-2981-Royalties.
/// @dev Sicherheitsmodell:
///  - Nur der Owner mintet (kuratierte Drops, kein offener Public Mint, kein Ether im Contract).
///  - Ownable2Step verhindert Owner-Transfer an falsche Adressen.
///  - baseURI ist bis freezeMetadata() aenderbar, danach unveraenderlich (EIP-4906 Event).
///  - Token-IDs 1..MAX_SUPPLY, jede ID genau einmal.
contract BlueDimensionGenesis is ERC721, ERC2981, Ownable2Step {
    using Strings for uint256;

    uint256 public immutable MAX_SUPPLY;
    uint96 public constant MAX_ROYALTY_BPS = 1_000; // 10 % Obergrenze

    string private _baseTokenURI;
    string private _contractURI;
    bool public metadataFrozen;
    uint256 public totalSupply;

    error InvalidTokenId(uint256 tokenId);
    error MetadataIsFrozen();
    error RoyaltyTooHigh(uint96 bps);
    error EmptyURI();

    /// @dev EIP-4906
    event BatchMetadataUpdate(uint256 fromTokenId, uint256 toTokenId);
    event ContractURIUpdated();
    event PermanentURI(string value, uint256 indexed id);

    constructor(
        address initialOwner,
        uint256 maxSupply_,
        string memory baseURI_,
        string memory contractURI_,
        address royaltyReceiver,
        uint96 royaltyBps
    ) ERC721("Blue Dimension Genesis", "BDG") Ownable(initialOwner) {
        if (royaltyBps > MAX_ROYALTY_BPS) revert RoyaltyTooHigh(royaltyBps);
        if (bytes(baseURI_).length == 0 || bytes(contractURI_).length == 0) revert EmptyURI();
        MAX_SUPPLY = maxSupply_;
        _baseTokenURI = baseURI_;
        _contractURI = contractURI_;
        _setDefaultRoyalty(royaltyReceiver, royaltyBps);
    }

    // ------------------------------------------------------------------ Mint

    function mint(address to, uint256 tokenId) external onlyOwner {
        _mintChecked(to, tokenId);
    }

    function mintBatch(address to, uint256[] calldata tokenIds) external onlyOwner {
        for (uint256 i; i < tokenIds.length; ++i) {
            _mintChecked(to, tokenIds[i]);
        }
    }

    function _mintChecked(address to, uint256 tokenId) private {
        if (tokenId == 0 || tokenId > MAX_SUPPLY) revert InvalidTokenId(tokenId);
        _safeMint(to, tokenId); // revertiert bei bereits existierender ID
        unchecked {
            ++totalSupply;
        }
    }

    // -------------------------------------------------------------- Metadata

    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        return string.concat(_baseTokenURI, tokenId.toString(), ".json");
    }

    function contractURI() external view returns (string memory) {
        return _contractURI;
    }

    function setBaseURI(string calldata newBaseURI) external onlyOwner {
        if (metadataFrozen) revert MetadataIsFrozen();
        if (bytes(newBaseURI).length == 0) revert EmptyURI();
        _baseTokenURI = newBaseURI;
        emit BatchMetadataUpdate(1, MAX_SUPPLY);
    }

    function setContractURI(string calldata newContractURI) external onlyOwner {
        if (metadataFrozen) revert MetadataIsFrozen();
        if (bytes(newContractURI).length == 0) revert EmptyURI();
        _contractURI = newContractURI;
        emit ContractURIUpdated();
    }

    /// @notice Irreversibel. Danach sind Token- und Collection-Metadaten permanent.
    function freezeMetadata() external onlyOwner {
        if (metadataFrozen) revert MetadataIsFrozen();
        metadataFrozen = true;
        for (uint256 id = 1; id <= MAX_SUPPLY; ++id) {
            emit PermanentURI(string.concat(_baseTokenURI, id.toString(), ".json"), id);
        }
    }

    // ------------------------------------------------------------- Royalties

    function setDefaultRoyalty(address receiver, uint96 bps) external onlyOwner {
        if (bps > MAX_ROYALTY_BPS) revert RoyaltyTooHigh(bps);
        _setDefaultRoyalty(receiver, bps);
    }

    // --------------------------------------------------------------- ERC-165

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, ERC2981) returns (bool) {
        return interfaceId == 0x49064906 // EIP-4906
            || super.supportsInterface(interfaceId);
    }
}
