//
//  CryptoStorageCipherTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
@testable import PosteRestante

final class CryptoStorageCipherTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.storage.cipher"
	private var sut: CryptoStorageManager!
	
	override func setUp() {
		super.setUp()
		sut = CryptoStorageManager(service: testService, account: "cipher-test-\(UUID().uuidString)")
	}
	
	override func tearDown() {
		try? sut.deleteStorageKey()
		sut = nil
		super.tearDown()
	}
	
	func test_encryptAndDecrypt_roundTripPreservesOriginalData() throws {
		let payload = "Sensitive user record to be stored securely.".data(using: .utf8)!
		
		let encrypted = try sut.encrypt(payload)
		let decrypted = try sut.decrypt(encrypted)
		
		XCTAssertEqual(decrypted, payload)
		XCTAssertEqual(String(data: decrypted, encoding: .utf8), "Sensitive user record to be stored securely.")
	}
	
	func test_encrypt_handlesEmptyData() throws {
		let emptyPayload = Data()
		
		let encrypted = try sut.encrypt(emptyPayload)
		let decrypted = try sut.decrypt(encrypted)
		
		XCTAssertEqual(decrypted, emptyPayload)
		// Combined AES-GCM overhead: 12-byte Nonce + 0-byte Ciphertext + 16-byte Tag = 28 bytes[cite: 3]
		XCTAssertEqual(encrypted.count, 28)
	}
	
	func test_encrypt_producesCombinedGCMContainerWithExpectedOverhead() throws {
		let payload = Data(repeating: 0x42, count: 100)
		
		let encrypted = try sut.encrypt(payload)
		
		// 12-byte Nonce + 100-byte Ciphertext + 16-byte Tag = 128 bytes[cite: 3]
		XCTAssertEqual(encrypted.count, 100 + 28)
	}
	
	func test_encrypt_usesRandomNonceForEachCall() throws {
		let payload = "Identical message".data(using: .utf8)!
		
		let cipher1 = try sut.encrypt(payload)
		let cipher2 = try sut.encrypt(payload)
		
		// Nonce is the first 12 bytes of combined AES-GCM data[cite: 3]
		let nonce1 = cipher1.prefix(12)
		let nonce2 = cipher2.prefix(12)
		
		XCTAssertNotEqual(cipher1, cipher2)
		XCTAssertNotEqual(nonce1, nonce2)
	}
}
