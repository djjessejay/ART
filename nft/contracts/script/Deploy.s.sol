// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

import {Script, console2} from "forge-std/Script.sol";
import {BlueDimensionGenesis} from "../src/BlueDimensionGenesis.sol";

/// Deployment ueber Hardware-Wallet oder Keystore, nie mit Klartext-Private-Key:
///   forge script script/Deploy.s.sol --rpc-url $RPC_URL --ledger --sender $OWNER --broadcast --verify
/// Pflicht-Variablen: OWNER, METADATA_CID, ROYALTY_RECEIVER
/// Optional: MAX_SUPPLY (7), ROYALTY_BPS (750), MINT_TO (leer = kein Mint)
contract Deploy is Script {
    function run() external returns (BlueDimensionGenesis nft) {
        address owner = vm.envAddress("OWNER");
        string memory cid = vm.envString("METADATA_CID");
        address royaltyReceiver = vm.envAddress("ROYALTY_RECEIVER");
        uint256 maxSupply = vm.envOr("MAX_SUPPLY", uint256(7));
        uint96 bps = uint96(vm.envOr("ROYALTY_BPS", uint256(750)));
        address mintTo = vm.envOr("MINT_TO", address(0));

        string memory base = string.concat("ipfs://", cid, "/metadata/");
        string memory curi = string.concat("ipfs://", cid, "/collection.json");

        vm.startBroadcast(owner);
        nft = new BlueDimensionGenesis(owner, maxSupply, base, curi, royaltyReceiver, bps);
        if (mintTo != address(0)) {
            uint256[] memory ids = new uint256[](maxSupply);
            for (uint256 i; i < maxSupply; ++i) ids[i] = i + 1;
            nft.mintBatch(mintTo, ids);
        }
        vm.stopBroadcast();

        console2.log("BlueDimensionGenesis:", address(nft));
        console2.log("baseURI:", base);
    }
}
