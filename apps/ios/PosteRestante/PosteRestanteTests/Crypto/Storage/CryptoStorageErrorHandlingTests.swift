//
//  CryptoStorageErrorHandlingTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
@testable import PosteRestante

final class CryptoStorageErrorHandlingTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.storage.security"
	private var sut: CryptoStorageManager!
	private var foreignSut: CryptoStorageManager!
	
	override func setUp() {
		super.setUp()
		sut = CryptoStorageManager(service: testService, account: "sec-test-\(UUID().uuidString)")
		foreignSut = CryptoStorageManager(service: testService, account: "foreign-sec-test-\(UUID().uuidString)")
	}
	
	override func tearDown() {
		try? sut.deleteStorageKey()
		try? foreignSut.deleteStorageKey()
		sut = nil
		foreignSut = nil
		super.tearDown()
	}
	
	func test_decrypt_throwsOnTamperedCiphertext() throws {
		let payload = "Tamper resistance test".data(using: .utf8)!
		var encrypted = try sut.encrypt(payload)
		
		// Flip bits in the middle of ciphertext
		let tamperIndex = 15
		encrypted[tamperIndex] ^= 0xFF
		
		XCTAssertThrowsError(try sut.decrypt(encrypted)) { error in
			guard case CryptoStorageError.decryptionFailed = error else {
				return XCTFail("Expected CryptoStorageError.decryptionFailed, got \(error)")
			}
		}
	}
	
	func test_decrypt_throwsOnTruncatedPayload() {
		// Minimum combined size is 28 bytes (12 nonce + 16 tag)[cite: 3]
		let shortPayload = Data(repeating: 0xAA, count: 27)
		
		XCTAssertThrowsError(try sut.decrypt(shortPayload)) { error in
			guard case CryptoStorageError.decryptionFailed = error else {
				return XCTFail("Expected CryptoStorageError.decryptionFailed, got \(error)")
			}
		}
	}
	
	func test_decrypt_failsWhenDecryptedWithDifferentKey() throws {
		let payload = "Secret cross-key message".data(using: .utf8)!
		let encrypted = try sut.encrypt(payload)
		
		// Attempt decrypting payload with a different master key
		XCTAssertThrowsError(try foreignSut.decrypt(encrypted)) { error in
			guard case CryptoStorageError.decryptionFailed = error else {
				return XCTFail("Expected CryptoStorageError.decryptionFailed, got \(error)")
			}
		}
	}
	
	func test_deleteStorageKey_succeedsWhenItemDoesNotExist() {
		XCTAssertNoThrow(try sut.deleteStorageKey())
	}
}
