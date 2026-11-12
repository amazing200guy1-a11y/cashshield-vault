/**
 * CASHSHIELD-VAULT TYPESCRIPT SDK
 * Bitcoin Cash UTXO covenant interaction and heartbeat management.
 */

export interface VaultMetadata {
  vaultId: string;
  ownerAddress: string;
  heirAddress: string;
  reserveBch: number;
  heartbeatIntervalDays: number;
  lastHeartbeatEpoch: number;
  covenantHash: string;
}

export class CashShieldClient {
  public static isOverdue(vault: VaultMetadata, currentEpoch: number): boolean {
    const intervalSeconds = vault.heartbeatIntervalDays * 86400;
    return currentEpoch >= (vault.lastHeartbeatEpoch + intervalSeconds);
  }

  public static formatBchSatoshis(bch: number): bigint {
    return BigInt(Math.round(bch * 100_000_000));
  }
}
