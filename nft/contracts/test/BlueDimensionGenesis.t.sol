// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

import {Test} from "forge-std/Test.sol";
import {BlueDimensionGenesis} from "../src/BlueDimensionGenesis.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IERC721Errors} from "@openzeppelin/contracts/interfaces/draft-IERC6093.sol";

contract BlueDimensionGenesisTest is Test {
    BlueDimensionGenesis nft;
    address owner = makeAddr("owner");
    address royalty = makeAddr("royalty");
    address collector = makeAddr("collector");
    address attacker = makeAddr("attacker");

    string constant BASE = "ipfs://bafyMETA/";
    string constant CURI = "ipfs://bafyMETA/collection.json";

    function setUp() public {
        nft = new BlueDimensionGenesis(owner, 7, BASE, CURI, royalty, 750);
    }

    function test_Metadata() public {
        vm.prank(owner);
        nft.mint(collector, 1);
        assertEq(nft.tokenURI(1), "ipfs://bafyMETA/1.json");
        assertEq(nft.contractURI(), CURI);
        assertEq(nft.ownerOf(1), collector);
        assertEq(nft.totalSupply(), 1);
    }

    function test_MintBatchAllSeven() public {
        uint256[] memory ids = new uint256[](7);
        for (uint256 i; i < 7; ++i) ids[i] = i + 1;
        vm.prank(owner);
        nft.mintBatch(owner, ids);
        assertEq(nft.totalSupply(), 7);
        assertEq(nft.balanceOf(owner), 7);
    }

    function test_RevertWhen_IdOutOfRange() public {
        vm.startPrank(owner);
        vm.expectRevert(abi.encodeWithSelector(BlueDimensionGenesis.InvalidTokenId.selector, 0));
        nft.mint(collector, 0);
        vm.expectRevert(abi.encodeWithSelector(BlueDimensionGenesis.InvalidTokenId.selector, 8));
        nft.mint(collector, 8);
        vm.stopPrank();
    }

    function test_RevertWhen_DoubleMint() public {
        vm.startPrank(owner);
        nft.mint(collector, 3);
        vm.expectRevert(abi.encodeWithSelector(IERC721Errors.ERC721InvalidSender.selector, address(0)));
        nft.mint(collector, 3);
        vm.stopPrank();
    }

    function test_RevertWhen_NonOwnerMints() public {
        vm.prank(attacker);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, attacker));
        nft.mint(attacker, 1);
    }

    function test_Royalty() public view {
        (address recv, uint256 amount) = nft.royaltyInfo(1, 1 ether);
        assertEq(recv, royalty);
        assertEq(amount, 0.075 ether);
    }

    function test_RevertWhen_RoyaltyTooHigh() public {
        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(BlueDimensionGenesis.RoyaltyTooHigh.selector, uint96(1001)));
        nft.setDefaultRoyalty(royalty, 1001);
    }

    function test_FreezeLocksMetadata() public {
        vm.startPrank(owner);
        nft.setBaseURI("ipfs://bafyNEW/");
        nft.freezeMetadata();
        assertTrue(nft.metadataFrozen());
        vm.expectRevert(BlueDimensionGenesis.MetadataIsFrozen.selector);
        nft.setBaseURI("ipfs://bafyEVIL/");
        vm.expectRevert(BlueDimensionGenesis.MetadataIsFrozen.selector);
        nft.setContractURI("ipfs://bafyEVIL/c.json");
        vm.stopPrank();
    }

    function test_SupportsInterfaces() public view {
        assertTrue(nft.supportsInterface(0x80ac58cd)); // ERC-721
        assertTrue(nft.supportsInterface(0x2a55205a)); // ERC-2981
        assertTrue(nft.supportsInterface(0x49064906)); // EIP-4906
    }

    function test_TwoStepOwnership() public {
        vm.prank(owner);
        nft.transferOwnership(collector);
        assertEq(nft.owner(), owner);
        vm.prank(collector);
        nft.acceptOwnership();
        assertEq(nft.owner(), collector);
    }

    function testFuzz_OnlyValidIds(uint256 id) public {
        vm.prank(owner);
        if (id == 0 || id > 7) {
            vm.expectRevert(abi.encodeWithSelector(BlueDimensionGenesis.InvalidTokenId.selector, id));
            nft.mint(collector, id);
        } else {
            nft.mint(collector, id);
            assertEq(nft.ownerOf(id), collector);
        }
    }
}
