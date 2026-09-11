//
//  CryptoStorageConcurrencyTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
@testable import PosteRestante

final class CryptoStorageConcurrencyTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.storage.concurrency"
	private var sut: CryptoStorageManager!
	
	override func setUp() {
		super.setUp()
		sut = CryptoStorageManager(service: testService, account: "concurrent-storage-\(UUID().uuidString)")
	}
	
	override func tearDown() {
		try? sut.deleteStorageKey()
		sut = nil
		super.tearDown()
	}
	
	func test_concurrentEncryptDecryptAndPurge_maintainsDataIntegrity() {
		let expectation = expectation(description: "Concurrent crypto operations finished")
		expectation.expectedFulfillmentCount = 40
		
		let queue = DispatchQueue(label: "id.reishandy.storage.concurrentQueue", attributes: .concurrent)
		let samplePayload = "Multi-threaded storage operation".data(using: .utf8)!
		
		for i in 0..<40 {
			queue.async {
				do {
					if i % 10 == 0 {
						self.sut.purgeMemoryCache()
					}
					let encrypted = try self.sut.encrypt(samplePayload)
					let decrypted = try self.sut.decrypt(encrypted)
					XCTAssertEqual(decrypted, samplePayload)
				} catch {
					XCTFail("Concurrent crypto operation failed: \(error)")
				}
				expectation.fulfill()
			}
		}
		
		wait(for: [expectation], timeout: 5.0)
	}
}
