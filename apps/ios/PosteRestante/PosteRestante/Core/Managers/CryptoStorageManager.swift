//
//  CryptoStorageManager.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import Foundation
import CryptoKit
import Security
#if canImport(UIKit)
import UIKit
#endif

public final class CryptoStorageManager: @unchecked Sendable {
	public static let shared = CryptoStorageManager()
	
	private let service: String
	private let account: String
	
	private var cachedKey: SymmetricKey?
	private let lock = NSLock()
	private var observerToken: (any NSObjectProtocol)?
	
	public init(
		service: String = "id.reishandy.PosteRestante.storage",
		account: String = "aes256-device"
	) {
		self.service = service
		self.account = account
		
#if canImport(UIKit)
		self.observerToken = NotificationCenter.default.addObserver(
			forName: UIApplication.protectedDataWillBecomeUnavailableNotification,
			object: nil,
			queue: nil
		) { [weak self] _ in
			self?.purgeMemoryCache()
		}
#endif
	}
	
	deinit {
#if canImport(UIKit)
		if let observerToken {
			NotificationCenter.default.removeObserver(observerToken)
		}
#endif
	}
	
	// MARK: - Key Lifecycle
	
	/// Explicitly purges the symmetric key from RAM.
	public func purgeMemoryCache() {
		lock.lock()
		defer { lock.unlock() }
		cachedKey = nil
	}
	
	/// Returns the cached symmetric key, loads it from Keychain, or generates a new one.
	public func getOrCreateMasterKey() throws -> SymmetricKey {
		lock.lock()
		defer { lock.unlock() }
		
		if let key = cachedKey {
			return key
		}
		
		if let existingKeyData = try loadKeyDataFromKeychain() {
			let key = SymmetricKey(data: existingKeyData)
			self.cachedKey = key
			return key
		}
		
		// Generate a new 256-bit AES master key
		let newKey = SymmetricKey(size: .bits256)
		let keyData = newKey.withUnsafeBytes { Data($0) }
		try saveKeyDataToKeychain(keyData)
		self.cachedKey = newKey
		return newKey
	}
	
	/// Deletes the master key from the Keychain and purges the in-memory cache.
	public func deleteStorageKey() throws {
		lock.lock()
		defer { lock.unlock() }
		
		cachedKey = nil
		
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account
		]
		
		let status = SecItemDelete(query as CFDictionary)
		guard status == errSecSuccess || status == errSecItemNotFound else {
			throw CryptoStorageError.keychainOperationFailed(status: status)
		}
	}
	
	// MARK: - Encryption / Decryption
	
	/// Encrypts plaintext into a combined AES-GCM container: 12-byte Nonce || Ciphertext || 16-byte Tag
	public func encrypt(_ plaintext: Data) throws -> Data {
		let key = try getOrCreateMasterKey()
		do {
			let sealedBox = try AES.GCM.seal(plaintext, using: key)
			guard let combined = sealedBox.combined else {
				throw CryptoStorageError.encryptionFailed
			}
			return combined
		} catch {
			throw CryptoStorageError.encryptionFailed
		}
	}
	
	/// Decrypts a combined AES-GCM container payload
	public func decrypt(_ combinedPayload: Data) throws -> Data {
		let key = try getOrCreateMasterKey()
		do {
			let sealedBox = try AES.GCM.SealedBox(combined: combinedPayload)
			return try AES.GCM.open(sealedBox, using: key)
		} catch {
			throw CryptoStorageError.decryptionFailed
		}
	}
	
	// MARK: - Private Helpers
	
	private func saveKeyDataToKeychain(_ data: Data) throws {
		let query: [String: Any] = [
			kSecClass as String: kSecClassGenericPassword,
			kSecAttrService as String: service,
			kSecAttrAccount as String: account,
			kSecValueData as String: data,
			kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
		]
		
		SecItemDelete(query as CFDictionary)
		
		let status = SecItemAdd(query as CFDictionary, nil)
		guard status == errSecSuccess else {
			throw CryptoStorageError.keychainOperationFailed(status: status)
		}
	}
	
	private func loadKeyDataFromKeychain() throws -> Data? {
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
				throw CryptoStorageError.invalidKeychainData
			}
			guard data.count == 32 else {
				throw CryptoStorageError.invalidKeySize(expected: 32, actual: data.count)
			}
			return data
		case errSecItemNotFound:
			return nil
		case errSecInteractionNotAllowed:
			throw CryptoStorageError.deviceLocked
		default:
			throw CryptoStorageError.keychainOperationFailed(status: status)
		}
	}
}
