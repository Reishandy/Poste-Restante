import Foundation
import CryptoKit
import Security

public actor CryptoIdentityManager {
	public static let shared = CryptoIdentityManager()
	
	private static let protocolSalt = Data("PosteRestante-v1-Handshake-Salt".utf8)
	private static let contextPrefix = Data("PosteRestante-v1-MasterSecret".utf8)
	
	private let service: String
	private let account: String
	
	public init(
		service: String = "id.reishandy.PosteRestante.identity",
		account: String = "x25519-device"
	) {
		self.service = service
		self.account = account
	}
	
	// MARK: - Lifecycle
	
	public func getOrCreatePrivateKey() throws -> Curve25519.KeyAgreement.PrivateKey {
		if let existingKey = try loadPrivateKey() {
			return existingKey
		}
		
		let newKey = Curve25519.KeyAgreement.PrivateKey()
		try savePrivateKey(newKey)
		
		return newKey
	}
	
	/// Exports the 32 raw bytes of the public key for exchange.
	public func exportPublicKeyBytes() throws -> Data {
		let privateKey = try getOrCreatePrivateKey()
		return privateKey.publicKey.rawRepresentation
	}
	
	public func deleteIdentityKey() throws {
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account
		]
		let status = SecItemDelete(query as CFDictionary)
		guard status == errSecSuccess || status == errSecItemNotFound else {
			throw CryptoIdentityError.keychainOperationFailed(status: status)
		}
	}
	
	// MARK: - Key Exchange
	
	/// Performs X25519 ECDH and derives a single 256-bit symmetric master secret via HKDF-SHA256.
	/// Binds lexicographically sorted public keys in HKDF context info.
	public func deriveSharedMasterSecret(
		peerPublicKeyBytes: Data
	) throws -> SymmetricKey {
		guard peerPublicKeyBytes.count == 32 else {
			throw CryptoIdentityError.invalidKeySize(expected: 32, actual: peerPublicKeyBytes.count)
		}
		
		let myPrivateKey = try getOrCreatePrivateKey()
		let myPublicKeyBytes = myPrivateKey.publicKey.rawRepresentation
		
		guard peerPublicKeyBytes != myPublicKeyBytes else {
			throw CryptoIdentityError.selfHandshakeNotPermitted
		}
		
		let peerPublicKey = try Curve25519.KeyAgreement.PublicKey(rawRepresentation: peerPublicKeyBytes)
		let sharedSecret = try myPrivateKey.sharedSecretFromKeyAgreement(with: peerPublicKey)
		
		// Deterministic public-key sorting for symmetric context binding
		let isMyKeyFirst = myPublicKeyBytes.lexicographicallyPrecedes(peerPublicKeyBytes)
		let firstKey = isMyKeyFirst ? myPublicKeyBytes : peerPublicKeyBytes
		let secondKey = isMyKeyFirst ? peerPublicKeyBytes : myPublicKeyBytes
		
		let hkdfInfo = Self.contextPrefix + firstKey + secondKey
		
		return sharedSecret.hkdfDerivedSymmetricKey(
			using: SHA256.self,
			salt: Self.protocolSalt,
			sharedInfo: hkdfInfo,
			outputByteCount: 32
		)
	}
	
	// MARK: - Private Helpers
	
	private func savePrivateKey(_ key: Curve25519.KeyAgreement.PrivateKey) throws {
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account,
			kSecValueData as String: key.rawRepresentation,
			kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
		]
		
		// Clear existing entry if any
		SecItemDelete(query as CFDictionary)
		
		let status = SecItemAdd(query as CFDictionary, nil)
		guard status == errSecSuccess else {
			throw CryptoIdentityError.keychainOperationFailed(status: status)
		}
	}
	
	private func loadPrivateKey() throws -> Curve25519.KeyAgreement.PrivateKey? {
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account,
			kSecReturnData as String: true,
			kSecMatchLimit as String: kSecMatchLimitOne
		]
		
		var item: CFTypeRef?
		let status = SecItemCopyMatching(query as CFDictionary, &item)
		
		switch status {
		case errSecSuccess:
			guard let data = item as? Data else {
				throw CryptoIdentityError.invalidKeychainData
			}
			guard data.count == 32 else {
				throw CryptoIdentityError.invalidKeySize(expected: 32, actual: data.count)
			}
			return try Curve25519.KeyAgreement.PrivateKey(rawRepresentation: data)
		case errSecItemNotFound:
			return nil
		default:
			throw CryptoIdentityError.keychainOperationFailed(status: status)
		}
	}
}
